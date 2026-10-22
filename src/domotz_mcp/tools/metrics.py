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
"""Device variables (metrics) and custom SNMP sensors, with their history."""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import DomotzClient
from ._common import (
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


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def domotz_metrics_variables_list(
        agent_id: AgentId,
        device_id: DeviceId,
        page_size: Annotated[int | None, Field(description="Variables per page (max 200).", ge=1, le=200)] = None,
        page_number: Annotated[int | None, Field(description="Page number, from 0.", ge=0)] = None,
        has_history: Annotated[bool | None, Field(description="Only variables that keep a value history.")] = None,
        offset: Offset = None,
    ) -> str:
        """List a device's monitored variables (SNMP / driver metrics) with current value and unit."""

        async def action(client: DomotzClient) -> Any:
            paging, number, size, start = locate(offset, page_number, page_size, VARIABLE_DEFAULT_PAGE_SIZE)
            variables = await client.get(f"agent/{agent_id}/device/{device_id}/variable", paging | {"has_history": has_history})
            if not isinstance(variables, list):
                return variables
            return page_result("variables", variables, number, size, start)

        return await run_tool("domotz_metrics_variables_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_metrics_variable_history(
        agent_id: AgentId,
        device_id: DeviceId,
        variable_id: Annotated[int, Field(description="Variable id from domotz_metrics_variables_list.", ge=1)],
        from_time: From = None,
        to_time: To = None,
    ) -> str:
        """Get the value history (time series) of one device variable over a window."""

        async def action(client: DomotzClient) -> Any:
            path = f"agent/{agent_id}/device/{device_id}/variable/{variable_id}/history"
            return await client.get(path, window(from_time, to_time))

        return await run_tool("domotz_metrics_variable_history", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_metrics_snmp_sensors_list(agent_id: AgentId, device_id: DeviceId) -> str:
        """List the custom SNMP sensors configured on a device (OID, name, value type, last value)."""

        async def action(client: DomotzClient) -> Any:
            return await client.get(f"agent/{agent_id}/device/{device_id}/eye/snmp")

        return await run_tool("domotz_metrics_snmp_sensors_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_metrics_sensor_history(
        agent_id: AgentId,
        device_id: DeviceId,
        sensor_id: Annotated[int, Field(description="SNMP sensor id from domotz_metrics_snmp_sensors_list.", ge=1)],
        from_time: From = None,
        to_time: To = None,
    ) -> str:
        """Get the value history of one custom SNMP sensor over a window."""

        async def action(client: DomotzClient) -> Any:
            path = f"agent/{agent_id}/device/{device_id}/eye/snmp/{sensor_id}/history"
            return await client.get(path, window(from_time, to_time))

        return await run_tool("domotz_metrics_sensor_history", client_factory, action)
