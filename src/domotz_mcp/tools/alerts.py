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
"""Alert profiles and the profiles bound to devices."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..api_client import DomotzClient
from ._common import READ_ONLY, AgentId, ClientFactory, DeviceId, run_tool


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
