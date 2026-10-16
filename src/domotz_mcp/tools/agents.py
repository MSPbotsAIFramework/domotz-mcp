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
"""Collectors (agents): one per monitored site."""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import DomotzClient
from ._common import READ_ONLY, AgentId, ClientFactory, run_tool


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def domotz_agents_list(
        display_name: Annotated[str | None, Field(description="Only collectors whose name contains this text.")] = None,
        page_size: Annotated[int | None, Field(description="Collectors per page.", ge=1, le=1000)] = None,
        page_number: Annotated[int | None, Field(description="Page number, from 0.", ge=0)] = None,
    ) -> str:
        """List Domotz collectors (one per site) with status, IP address, location and licence."""

        async def action(client: DomotzClient) -> dict:
            params = {"display_name": (display_name or "").strip() or None, "page_size": page_size, "page_number": page_number}
            agents = await client.get("agent", params) or []
            return {"agents": agents, "count": len(agents) if isinstance(agents, list) else None}

        return await run_tool("domotz_agents_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def domotz_agents_get(agent_id: AgentId) -> str:
        """Get one collector's details: status, version, location, network, licence and access rights."""

        async def action(client: DomotzClient) -> Any:
            return await client.get(f"agent/{agent_id}")

        return await run_tool("domotz_agents_get", client_factory, action)
