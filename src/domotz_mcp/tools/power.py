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
"""Smart power outlets (PDUs / smart plugs) and switching them."""

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import DomotzClient
from ._common import POWER_ACTION, READ_ONLY, AgentId, ClientFactory, run_tool

PowerDeviceId = Annotated[int, Field(description="Device id of the PDU / smart plug.", ge=1)]


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def domotz_power_outlets_list(agent_id: AgentId, device_id: PowerDeviceId) -> str:
        """List a PDU's or smart plug's outlets with their power state and whether they can be switched."""

        async def action(client: DomotzClient) -> dict:
            outlets = await client.get(f"agent/{agent_id}/device/{device_id}/power-outlet") or []
            return {"agent_id": agent_id, "device_id": device_id, "outlets": outlets, "count": len(outlets) if isinstance(outlets, list) else None}

        return await run_tool("domotz_power_outlets_list", client_factory, action)

    @mcp.tool(annotations=POWER_ACTION)
    async def domotz_power_outlet_control(
        agent_id: AgentId,
        device_id: PowerDeviceId,
        outlet_id: Annotated[int | str, Field(description="Outlet id from domotz_power_outlets_list.")],
        action: Annotated[Literal["on", "off", "cycle"], Field(description="on, off, or cycle (off then on).")],
        confirm: Annotated[bool, Field(description="Must be true, set only after the user approved this exact action.")],
    ) -> str:
        """Switch a power outlet on, off or power-cycle it; cuts power to the plugged-in equipment.

        Only when the user explicitly asks, for the exact outlet, with confirm: true.
        """

        async def run(client: DomotzClient) -> Any:
            outlet = str(outlet_id).strip()
            if not outlet:
                raise ValueError("outlet_id must not be blank.")
            if confirm is not True:
                return {
                    "sent": False,
                    "message": f"Not sent. Ask the user to approve turning outlet {outlet} {action}, then call again with confirm: true.",
                }
            await client.post(f"agent/{agent_id}/device/{device_id}/power-outlet/{outlet}/action/{action}")
            return {
                "sent": True,
                "agent_id": agent_id,
                "device_id": device_id,
                "outlet_id": outlet,
                "action": action,
                "note": "Domotz accepted the request (it runs asynchronously); check domotz_power_outlets_list for the new state.",
            }

        return await run_tool("domotz_power_outlet_control", client_factory, run)
