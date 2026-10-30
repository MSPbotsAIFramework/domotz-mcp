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
"""Alert profiles and the profiles bound to devices.

Also: alerts that have fired (list / resolve) and Alert Rules (list / get / bind / unbind
to a collector or device) — PRD-21260.
"""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import DomotzClient
from ._common import (
    ALERT_ACTION,
    READ_ONLY,
    VARIABLE_DEFAULT_PAGE_SIZE,
    AgentId,
    ClientFactory,
    DeviceId,
    From,
    Offset,
    To,
    locate,
    page_result,
    run_tool,
    window,
)

AlertId = Annotated[int, Field(description="Alert id from domotz_alerts_list.", ge=1)]
AlertRuleId = Annotated[int, Field(description="Alert Rule id from domotz_alert_rules_list.", ge=1)]
Confirm = Annotated[bool, Field(description="Must be true, set only after the user approved this exact action.")]


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def domotz_alerts_profiles_list() -> str:
        """List the alert profiles configured in the account (which events notify whom)."""

        async def action(client: DomotzClient) -> Any:
            return await client.get("alert-profile")

        return await run_tool("domotz_alerts_profiles_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_alerts_device_list(agent_id: AgentId, device_id: DeviceId) -> str:
        """List the alert profiles bound to one device."""

        async def action(client: DomotzClient) -> dict:
            # The API lists bindings for every device of a collector; keep this device's.
            bindings = await client.get(f"alert-profile/binding/agent/{agent_id}/device") or []
            rows = bindings if isinstance(bindings, list) else []
            mine = [b for b in rows if isinstance(b, dict) and str(b.get("device_id")) == str(device_id)]
            return {"agent_id": agent_id, "device_id": device_id, "bindings": mine, "count": len(mine)}

        return await run_tool("domotz_alerts_device_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_alerts_list(
        from_time: From,
        to_time: To,
        severity: Annotated[str | None, Field(description="Filter by severity, as Domotz reports it (e.g. high, medium, low).")] = None,
        status: Annotated[str | None, Field(description="Filter by alert status, as Domotz reports it (e.g. open, resolved).")] = None,
        alert_rule_id: Annotated[int | None, Field(description="Only alerts raised by this Alert Rule.", ge=1)] = None,
        agent_id: Annotated[int | None, Field(description="Only alerts for this collector.", ge=1)] = None,
        device_id: Annotated[int | None, Field(description="Only alerts for this device.", ge=1)] = None,
        page_size: Annotated[int | None, Field(description="Alerts per page (max 200).", ge=1, le=200)] = None,
        page_number: Annotated[int | None, Field(description="Page number, from 0.", ge=0)] = None,
        offset: Offset = None,
    ) -> str:
        """List alerts that fired in a time window (both from_time and to_time are required), newest first."""

        async def action(client: DomotzClient) -> dict:
            paging, number, size, start = locate(offset, page_number, page_size, VARIABLE_DEFAULT_PAGE_SIZE)
            params = window(from_time, to_time) | {
                "severity": severity,
                "status": status,
                "alert_rule_id": alert_rule_id,
                "agent_id": agent_id,
                "device_id": device_id,
            } | paging
            alerts = await client.get("alert", params) or []
            if not isinstance(alerts, list):
                return {"alerts": alerts, "count": None}
            return page_result("alerts", alerts, number, size, start)

        return await run_tool("domotz_alerts_list", client_factory, action)

    @mcp.tool(annotations=ALERT_ACTION)
    async def domotz_alerts_resolve(alert_id: AlertId, confirm: Confirm) -> str:
        """Mark a fired alert resolved.

        Only when the user explicitly asks, for the exact alert, with confirm: true.
        """

        async def action(client: DomotzClient) -> Any:
            if confirm is not True:
                return {
                    "sent": False,
                    "message": f"Not sent. Ask the user to approve resolving alert {alert_id}, then call again with confirm: true.",
                }
            await client.post(f"alert/{alert_id}/resolve")
            return {"sent": True, "alert_id": alert_id, "note": "Domotz accepted the request."}

        return await run_tool("domotz_alerts_resolve", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_alert_rules_list() -> str:
        """List the account's Alert Rules (the datapoint / condition / severity each one watches)."""

        async def action(client: DomotzClient) -> Any:
            return await client.get("alert-rule")

        return await run_tool("domotz_alert_rules_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_alert_rules_get(alert_rule_id: AlertRuleId) -> str:
        """Get one Alert Rule's details: datapoint, condition, severity and operands."""

        async def action(client: DomotzClient) -> Any:
            return await client.get(f"alert-rule/{alert_rule_id}")

        return await run_tool("domotz_alert_rules_get", client_factory, action)

    @mcp.tool(annotations=ALERT_ACTION)
    async def domotz_alert_rules_bind_agent(alert_rule_id: AlertRuleId, agent_id: AgentId, confirm: Confirm) -> str:
        """Attach an existing Alert Rule to a collector, so it starts watching that collector's devices.

        Only when the user explicitly asks, for the exact rule and collector, with confirm: true.
        """

        async def action(client: DomotzClient) -> Any:
            if confirm is not True:
                return {
                    "sent": False,
                    "message": f"Not sent. Ask the user to approve binding alert rule {alert_rule_id} to collector {agent_id}, then call again with confirm: true.",
                }
            await client.post(f"alert-rule/{alert_rule_id}/agent/{agent_id}/binding")
            return {"sent": True, "alert_rule_id": alert_rule_id, "agent_id": agent_id, "note": "Domotz accepted the request."}

        return await run_tool("domotz_alert_rules_bind_agent", client_factory, action)

    @mcp.tool(annotations=ALERT_ACTION)
    async def domotz_alert_rules_unbind_agent(alert_rule_id: AlertRuleId, agent_id: AgentId, confirm: Confirm) -> str:
        """Detach an Alert Rule from a collector, so it stops watching that collector's devices.

        Only when the user explicitly asks, for the exact rule and collector, with confirm: true.
        """

        async def action(client: DomotzClient) -> Any:
            if confirm is not True:
                return {
                    "sent": False,
                    "message": f"Not sent. Ask the user to approve unbinding alert rule {alert_rule_id} from collector {agent_id}, then call again with confirm: true.",
                }
            await client.delete(f"alert-rule/{alert_rule_id}/agent/{agent_id}/binding")
            return {"sent": True, "alert_rule_id": alert_rule_id, "agent_id": agent_id, "note": "Domotz accepted the request."}

        return await run_tool("domotz_alert_rules_unbind_agent", client_factory, action)

    @mcp.tool(annotations=ALERT_ACTION)
    async def domotz_alert_rules_bind_device(alert_rule_id: AlertRuleId, agent_id: AgentId, device_id: DeviceId, confirm: Confirm) -> str:
        """Attach an existing Alert Rule to one device, so it starts watching that device.

        Only when the user explicitly asks, for the exact rule and device, with confirm: true.
        """

        async def action(client: DomotzClient) -> Any:
            if confirm is not True:
                return {
                    "sent": False,
                    "message": f"Not sent. Ask the user to approve binding alert rule {alert_rule_id} to device {device_id}, then call again with confirm: true.",
                }
            await client.post(f"alert-rule/{alert_rule_id}/agent/{agent_id}/device/{device_id}/binding")
            return {
                "sent": True,
                "alert_rule_id": alert_rule_id,
                "agent_id": agent_id,
                "device_id": device_id,
                "note": "Domotz accepted the request.",
            }

        return await run_tool("domotz_alert_rules_bind_device", client_factory, action)

    @mcp.tool(annotations=ALERT_ACTION)
    async def domotz_alert_rules_unbind_device(alert_rule_id: AlertRuleId, agent_id: AgentId, device_id: DeviceId, confirm: Confirm) -> str:
        """Detach an Alert Rule from one device, so it stops watching that device.

        Only when the user explicitly asks, for the exact rule and device, with confirm: true.
        """

        async def action(client: DomotzClient) -> Any:
            if confirm is not True:
                return {
                    "sent": False,
                    "message": f"Not sent. Ask the user to approve unbinding alert rule {alert_rule_id} from device {device_id}, then call again with confirm: true.",
                }
            await client.delete(f"alert-rule/{alert_rule_id}/agent/{agent_id}/device/{device_id}/binding")
            return {
                "sent": True,
                "alert_rule_id": alert_rule_id,
                "agent_id": agent_id,
                "device_id": device_id,
                "note": "Domotz accepted the request.",
            }

        return await run_tool("domotz_alert_rules_unbind_device", client_factory, action)
