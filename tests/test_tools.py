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
"""tools/list snapshot and error-envelope mapping. No network access."""

import asyncio
import json

import pytest

from domotz_mcp.api_client import DomotzError
from domotz_mcp.server import INSTRUCTIONS, create_mcp_server

AD = {"agent_id", "device_id"}

# Tool names are a public contract: existing agents and tenant connections
# depend on them. Changing this snapshot is a breaking change.
EXPECTED_TOOLS: dict[str, set[str]] = {
    "domotz_navigate": {"domain"},
    "domotz_back": set(),
    "domotz_status": set(),
    "domotz_agents_list": set(),
    "domotz_agents_get": {"agent_id"},
    "domotz_devices_list": {"agent_id"},
    "domotz_devices_get": AD,
    "domotz_devices_uptime": AD,
    "domotz_devices_history": AD,
    "domotz_devices_inventory": AD,
    "domotz_metrics_variables_list": AD,
    "domotz_metrics_variable_history": AD | {"variable_id"},
    "domotz_metrics_snmp_sensors_list": AD,
    "domotz_metrics_sensor_history": AD | {"sensor_id"},
    "domotz_network_topology": {"agent_id"},
    "domotz_network_interfaces": {"agent_id"},
    "domotz_network_ip_conflicts": {"agent_id"},
    "domotz_alerts_profiles_list": set(),
    "domotz_alerts_device_list": AD,
    "domotz_power_outlets_list": AD,
    "domotz_power_outlet_control": AD | {"outlet_id", "action", "confirm"},
}
WRITE_TOOLS = {"domotz_power_outlet_control"}


@pytest.fixture(scope="module")
def tools():
    return {t.name: t for t in asyncio.run(create_mcp_server().list_tools())}


def test_all_tools_listed_without_navigation(tools):
    assert set(tools) == set(EXPECTED_TOOLS)


@pytest.mark.parametrize("name", sorted(EXPECTED_TOOLS))
def test_required_params(tools, name):
    assert set(tools[name].inputSchema.get("required", [])) == EXPECTED_TOOLS[name]


@pytest.mark.parametrize("name", sorted(EXPECTED_TOOLS))
def test_description_budget(tools, name):
    description = (tools[name].description or "").strip()
    assert description, f"{name} has no description"
    assert len(description) <= 500
    assert len(description.splitlines()[0]) <= 100


@pytest.mark.parametrize("name", sorted(EXPECTED_TOOLS))
def test_annotations_match_side_effects(tools, name):
    annotations = tools[name].annotations
    assert annotations is not None
    assert annotations.readOnlyHint is (name not in WRITE_TOOLS)
    assert bool(annotations.destructiveHint) is (name in WRITE_TOOLS)


def test_power_tool_says_when_to_use_it(tools):
    assert "explicitly asks" in tools["domotz_power_outlet_control"].description


def test_instructions_budget():
    assert len(INSTRUCTIONS) <= 1500


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (401, "unauthorized", False),
        (403, "unauthorized", False),
        (404, "not_found", False),
        (400, "invalid_argument", False),
        (429, "rate_limited", True),
        (500, "upstream_error", True),
        (0, "upstream_error", True),
    ],
)
def test_error_envelope(status, code, retryable):
    envelope = json.loads(DomotzError(status, "boom").to_envelope())
    assert envelope == {"error": {"code": code, "message": "boom", "retryable": retryable}}


def test_tool_without_credentials_returns_not_configured():
    content, _ = asyncio.run(create_mcp_server().call_tool("domotz_agents_list", {}))
    assert json.loads(content[0].text)["error"]["code"] == "not_configured"


def test_navigate_needs_no_credentials():
    content, _ = asyncio.run(create_mcp_server().call_tool("domotz_navigate", {"domain": "power"}))
    assert json.loads(content[0].text)["tools"] == ["domotz_power_outlets_list", "domotz_power_outlet_control"]
