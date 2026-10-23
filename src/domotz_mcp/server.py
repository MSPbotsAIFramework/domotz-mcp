# Copyright 2026 MSPbots.ai
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""FastMCP factory and the per-request credential middleware."""

import contextvars
import re
import uuid
from collections.abc import Callable
from urllib.parse import urlsplit

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ._arguments import EnvelopeFastMCP
from .api_client import DomotzClient, DomotzCredentials
from .config import API_HOST_SUFFIX, API_URL_TEMPLATE, DEFAULT_REGION, REGION_ALIASES, Settings

HEADER_API_KEY = "X-Domotz-API-Key"
HEADER_REGION = "X-Domotz-Region"

_PLACEHOLDER = re.compile(r"^\$\{.*\}$")

# Per-request isolation: the middleware sets these for the duration of one
# HTTP request and resets them in `finally`. Nothing credential-related is
# ever stored at module level.
_credentials_var: contextvars.ContextVar[DomotzCredentials | None] = contextvars.ContextVar(
    "domotz_credentials", default=None
)
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("domotz_request_id", default="-")

INSTRUCTIONS = (
    "Domotz monitors MSP client networks: a collector (agent) on each site "
    "discovers and watches every device on it, gathers SNMP / variable metrics "
    "and can switch smart power outlets.\n"
    "Usage:\n"
    "- Start with domotz_agents_list for agent_id values, then "
    "domotz_devices_list(agent_id) for device_id values.\n"
    "- Device health: domotz_devices_get, domotz_devices_uptime, "
    "domotz_devices_history (online / offline events), "
    "domotz_metrics_variables_list and the history tools; history tools take "
    "an optional ISO 8601 from / to window.\n"
    "- Site view: domotz_network_topology, domotz_network_interfaces, "
    "domotz_network_ip_conflicts.\n"
    "- Alerts: domotz_alerts_profiles_list and domotz_alerts_device_list "
    "(profiles bound to a device).\n"
    "- domotz_power_outlet_control switches an outlet on, off or power-cycles "
    "it, cutting power to what is plugged in: call it only when the user "
    "explicitly asks, for the exact outlet, with confirm: true.\n"
    "- The API key's daily call quota is limited; domotz_status shows usage."
)


def get_client_from_context() -> DomotzClient | None:
    """The client for the current request, or None outside a request."""
    credentials = _credentials_var.get()
    if credentials is None:
        return None
    return DomotzClient(credentials)


def _clean(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text or _PLACEHOLDER.match(text):
        return None
    return text


def resolve_base_url(region: str | None) -> str | None:
    """API base URL for a region name, alias or portal endpoint URL; None when not recognised."""
    if not region:
        return API_URL_TEMPLATE.format(region=DEFAULT_REGION)
    text = region.strip()
    if "://" in text:
        parts = urlsplit(text)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not host.endswith(API_HOST_SUFFIX):
            return None
        path = parts.path.rstrip("/")
        if not path.endswith("/public-api/v1"):
            path = "/public-api/v1"
        return f"https://{host}{path}"
    cell = REGION_ALIASES.get(text.lower())
    return API_URL_TEMPLATE.format(region=cell) if cell else None


class GatewayCredentialsMiddleware:
    """Reads X-Domotz-API-Key (and optional X-Domotz-Region) on /mcp requests; 401 when the key is missing.

    A malformed region does not block the request (tools/list must work with any
    values); tools report it instead.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        api_key = _clean(request.headers.get(HEADER_API_KEY))
        if not api_key:
            await JSONResponse(
                {
                    "error": "Missing credentials",
                    "message": f"Send the Domotz API key in {HEADER_API_KEY}",
                    "required_headers": [HEADER_API_KEY],
                    "optional_headers": [HEADER_REGION],
                },
                status_code=401,
            )(scope, receive, send)
            return
        base_url = resolve_base_url(_clean(request.headers.get(HEADER_REGION)))
        header_error = None
        if base_url is None:
            header_error = (
                f"{HEADER_REGION} must be us, eu, us-east-1, eu-west-1 or the https API endpoint "
                "shown in the Domotz portal"
            )
            base_url = API_URL_TEMPLATE.format(region=DEFAULT_REGION)

        request_id = (request.headers.get("x-request-id") or "").strip()[:64] or uuid.uuid4().hex[:12]
        creds_token = _credentials_var.set(DomotzCredentials(api_key, base_url, header_error))
        rid_token = request_id_var.set(request_id)
        try:
            await self.app(scope, receive, send)
        finally:
            _credentials_var.reset(creds_token)
            request_id_var.reset(rid_token)


def create_mcp_server(settings: Settings | None = None) -> FastMCP:
    """Build the FastMCP server and register every tool."""
    mcp = EnvelopeFastMCP(
        name="domotz-mcp",
        instructions=INSTRUCTIONS,
        # The service sits behind the gateway, so Host is never localhost;
        # DNS-rebinding protection would reject those requests with 421.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        stateless_http=True,
    )

    client_factory: Callable[[], DomotzClient | None] = get_client_from_context

    from .tools import agents, alerts, devices, metrics, navigation, network, power

    for module in (navigation, agents, devices, metrics, network, alerts, power):
        module.register(mcp, client_factory)

    return mcp
