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
"""Devices a collector discovered on its network."""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import DomotzClient
from ._common import READ_ONLY, AgentId, ClientFactory, DeviceId, From, To, run_tool, window


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def domotz_devices_list(
        agent_id: AgentId,
        show_hidden: Annotated[bool | None, Field(description="Include hidden devices.")] = None,
        show_excluded: Annotated[bool | None, Field(description="Include devices excluded from monitoring.")] = None,
    ) -> str:
        """List the devices on a collector's network: name, status, IP, MAC, type, vendor and importance."""

        async def action(client: DomotzClient) -> dict:
            devices = await client.get(f"agent/{agent_id}/device", {"show_hidden": show_hidden, "show_excluded": show_excluded}) or []
            summary: dict[str, int] = {}
            for device in devices if isinstance(devices, list) else []:
                status = str(device.get("status") or "UNKNOWN") if isinstance(device, dict) else "UNKNOWN"
                summary[status] = summary.get(status, 0) + 1
            return {"agent_id": agent_id, "devices": devices, "count": len(devices) if isinstance(devices, list) else None, "byStatus": summary}

        return await run_tool("domotz_devices_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_devices_get(agent_id: AgentId, device_id: DeviceId) -> str:
        """Get a device's full details: vendor, model, OS, IP / MAC, status, importance and details."""

        async def action(client: DomotzClient) -> Any:
            return await client.get(f"agent/{agent_id}/device/{device_id}")

        return await run_tool("domotz_devices_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_devices_uptime(agent_id: AgentId, device_id: DeviceId, from_time: From = None, to_time: To = None) -> str:
        """Get a device's uptime percentage over a window (default: Domotz's standard period)."""

        async def action(client: DomotzClient) -> Any:
            return await client.get(f"agent/{agent_id}/device/{device_id}/uptime", window(from_time, to_time))

        return await run_tool("domotz_devices_uptime", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_devices_history(agent_id: AgentId, device_id: DeviceId, from_time: From = None, to_time: To = None) -> str:
        """Get a device's state-change history (online / offline / down events) over a window."""

        async def action(client: DomotzClient) -> Any:
            events = await client.get(f"agent/{agent_id}/device/{device_id}/history/network/event", window(from_time, to_time))
            return {"agent_id": agent_id, "device_id": device_id, "events": events, "count": len(events) if isinstance(events, list) else None}

        return await run_tool("domotz_devices_history", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_devices_inventory(agent_id: AgentId, device_id: DeviceId) -> str:
        """Get a device's inventory fields (owner, location, notes and other custom fields)."""

        async def action(client: DomotzClient) -> Any:
            return await client.get(f"agent/{agent_id}/device/{device_id}/inventory")

        return await run_tool("domotz_devices_inventory", client_factory, action)
