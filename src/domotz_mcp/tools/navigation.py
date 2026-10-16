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
"""Discovery helpers kept for compatibility, plus the connection / quota check.

Every tool is listed from the first tools/list, so domotz_navigate and
domotz_back only describe tools; they keep no state.
"""

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .._json import compact as to_json
from ..api_client import DomotzClient
from ._common import LOCAL, READ_ONLY, ClientFactory, run_tool

DOMAINS: dict[str, tuple[str, list[str]]] = {
    "agents": ("Collectors (one per monitored site).", ["domotz_agents_list", "domotz_agents_get"]),
    "devices": (
        "Devices a collector discovered: details, uptime, online / offline history, inventory.",
        ["domotz_devices_list", "domotz_devices_get", "domotz_devices_uptime", "domotz_devices_history", "domotz_devices_inventory"],
    ),
    "metrics": (
        "Device variables (metrics) and custom SNMP sensors, with history.",
        [
            "domotz_metrics_variables_list",
            "domotz_metrics_variable_history",
            "domotz_metrics_snmp_sensors_list",
            "domotz_metrics_sensor_history",
        ],
    ),
    "network": (
        "Site topology, monitored networks and IP conflicts.",
        ["domotz_network_topology", "domotz_network_interfaces", "domotz_network_ip_conflicts"],
    ),
    "alerts": ("Alert profiles and the profiles bound to a device.", ["domotz_alerts_profiles_list", "domotz_alerts_device_list"]),
    "power": ("Smart power outlets: list, and switch on / off / cycle (changes power).", ["domotz_power_outlets_list", "domotz_power_outlet_control"]),
}

Domain = Literal["agents", "devices", "metrics", "network", "alerts", "power"]


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=LOCAL)
    async def domotz_navigate(domain: Annotated[Domain, Field(description="Area to describe.")]) -> str:
        """Describe the tools of one Domotz area. All tools are already callable; this changes nothing."""
        summary, tools = DOMAINS[domain]
        return to_json({"domain": domain, "summary": summary, "tools": tools})

    @mcp.tool(annotations=LOCAL)
    async def domotz_back() -> str:
        """List every Domotz area and its tools. All tools are already callable; this changes nothing."""
        return to_json({"domains": {name: {"summary": s, "tools": t} for name, (s, t) in DOMAINS.items()}})

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_status() -> str:
        """Check the Domotz connection and show the API key's call usage and limits."""

        async def action(client: DomotzClient) -> dict:
            usage = await client.get("meta/usage")
            return {"connected": True, "endpoint": client.base_url, "usage": usage, "domains": list(DOMAINS)}

        return await run_tool("domotz_status", client_factory, action)
