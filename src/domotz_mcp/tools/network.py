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
"""A collector's network: topology, monitored interfaces and IP conflicts."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..api_client import DomotzClient
from ._common import READ_ONLY, AgentId, ClientFactory, run_tool


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def domotz_network_topology(agent_id: AgentId) -> str:
        """Get a site's network topology: which devices connect to which switch ports / access points."""

        async def action(client: DomotzClient) -> Any:
            return await client.get(f"agent/{agent_id}/network-topology")

        return await run_tool("domotz_network_topology", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_network_interfaces(agent_id: AgentId) -> str:
        """List the networks (interfaces / subnets) a collector monitors."""

        async def action(client: DomotzClient) -> Any:
            return await client.get(f"agent/{agent_id}/network/interfaces")

        return await run_tool("domotz_network_interfaces", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_network_ip_conflicts(agent_id: AgentId) -> str:
        """List active IP address conflicts on a collector's network."""

        async def action(client: DomotzClient) -> Any:
            conflicts = await client.get(f"agent/{agent_id}/ip-conflict") or []
            return {"agent_id": agent_id, "conflicts": conflicts, "count": len(conflicts) if isinstance(conflicts, list) else None}

        return await run_tool("domotz_network_ip_conflicts", client_factory, action)
