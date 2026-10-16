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
"""Request shapes, retries and tool behaviour against a mocked Domotz API."""

import json

import httpx
import pytest

from domotz_mcp import api_client
from domotz_mcp.api_client import DomotzClient, DomotzCredentials, DomotzError
from domotz_mcp.server import _credentials_var, create_mcp_server

BASE = "https://api-us-east-1-cell-1.domotz.com/public-api/v1"
CREDS = DomotzCredentials("key-123", BASE)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(api_client.asyncio, "sleep", instant)


class Recorder:
    """Mock transport: replies by method + path below /public-api/v1/."""

    def __init__(self, routes=None, default=None):
        self.requests: list[httpx.Request] = []
        self.routes = routes or {}
        self.default = default if default is not None else []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path.removeprefix("/public-api/v1/")
        reply = self.routes.get(f"{request.method} {path}", self.routes.get(path, self.default))
        if callable(reply):
            return reply(request)
        return httpx.Response(200, json=reply)

    def calls(self, path: str, method: str | None = None) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path == f"/public-api/v1/{path}" and (method is None or r.method == method)]


async def _call(monkeypatch, recorder: Recorder, tool: str, args: dict):
    http = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
    monkeypatch.setattr(api_client, "_get_shared_http_client", lambda: http)
    ctx = _credentials_var.set(CREDS)
    try:
        content, _ = await create_mcp_server().call_tool(tool, args)
    finally:
        _credentials_var.reset(ctx)
    return json.loads(content[0].text)


def _client(recorder: Recorder) -> DomotzClient:
    return DomotzClient(CREDS, httpx.AsyncClient(transport=httpx.MockTransport(recorder)))


# ---- client ----------------------------------------------------------------


async def test_api_key_header_and_bool_params():
    rec = Recorder({"agent/1/device": []})
    await _client(rec).get("agent/1/device", {"show_hidden": True, "show_excluded": None})
    request = rec.requests[0]
    assert request.headers["X-Api-Key"] == "key-123"
    assert str(request.url) == f"{BASE}/agent/1/device?show_hidden=true"


async def test_get_retries_5xx_post_does_not():
    replies = iter([httpx.Response(503), httpx.Response(200, json=[])])
    rec = Recorder({"GET agent": lambda r: next(replies), "POST x": lambda r: httpx.Response(500)})
    client = _client(rec)
    await client.get("agent")
    with pytest.raises(DomotzError):
        await client.post("x")
    assert len(rec.calls("agent")) == 2 and len(rec.calls("x")) == 1


async def test_bad_key_is_unauthorized_without_leaking_it(monkeypatch):
    rec = Recorder({"agent": lambda r: httpx.Response(401, json={"message": "Unauthorized"})})
    result = await _call(monkeypatch, rec, "domotz_agents_list", {})
    assert result["error"]["code"] == "unauthorized"
    assert "key-123" not in json.dumps(result)


async def test_nested_error_description_is_used(monkeypatch):
    rec = Recorder({"agent": lambda r: httpx.Response(401, json={"error": {"code": None, "description": "Invalid API Key"}})})
    result = await _call(monkeypatch, rec, "domotz_agents_list", {})
    assert result["error"]["message"].endswith(": Invalid API Key")


async def test_quota_exhausted_is_rate_limited(monkeypatch):
    rec = Recorder({"agent": lambda r: httpx.Response(429, json={"message": "Too many requests"})})
    result = await _call(monkeypatch, rec, "domotz_agents_list", {})
    assert result["error"]["code"] == "rate_limited"
    assert len(rec.requests) == 3


# ---- tools -----------------------------------------------------------------


async def test_status_reports_usage(monkeypatch):
    rec = Recorder({"meta/usage": {"daily_limit": 1000, "current": 12}})
    result = await _call(monkeypatch, rec, "domotz_status", {})
    assert result["connected"] is True and result["usage"]["current"] == 12


async def test_agents_list_filters(monkeypatch):
    rec = Recorder({"agent": [{"id": 1}]})
    result = await _call(monkeypatch, rec, "domotz_agents_list", {"display_name": "HQ", "page_size": 10})
    assert rec.requests[0].url.params["display_name"] == "HQ"
    assert result["count"] == 1


async def test_devices_list_counts_status(monkeypatch):
    rec = Recorder({"agent/7/device": [{"id": 1, "status": "ONLINE"}, {"id": 2, "status": "DOWN"}, {"id": 3, "status": "ONLINE"}]})
    result = await _call(monkeypatch, rec, "domotz_devices_list", {"agent_id": 7})
    assert result["byStatus"] == {"ONLINE": 2, "DOWN": 1}


async def test_device_history_uses_state_change_events_with_window(monkeypatch):
    rec = Recorder({"agent/7/device/9/history/network/event": [{"type": "DOWN"}]})
    args = {"agent_id": 7, "device_id": 9, "from_time": "2026-06-01T00:00:00+02:00", "to_time": "2026-06-02"}
    result = await _call(monkeypatch, rec, "domotz_devices_history", args)
    params = rec.requests[0].url.params
    assert (params["from"], params["to"]) == ("2026-05-31T22:00:00Z", "2026-06-02T00:00:00Z")
    assert result["count"] == 1


async def test_bad_window_is_rejected(monkeypatch):
    rec = Recorder()
    result = await _call(monkeypatch, rec, "domotz_devices_uptime", {"agent_id": 7, "device_id": 9, "from_time": "yesterday"})
    assert result["error"]["code"] == "invalid_argument"
    result = await _call(monkeypatch, rec, "domotz_devices_uptime", {"agent_id": 7, "device_id": 9, "from_time": "2026-06-02", "to_time": "2026-06-01"})
    assert result["error"]["code"] == "invalid_argument"
    assert rec.requests == []


@pytest.mark.parametrize(
    "tool,args,path",
    [
        ("domotz_agents_get", {"agent_id": 7}, "agent/7"),
        ("domotz_devices_get", {"agent_id": 7, "device_id": 9}, "agent/7/device/9"),
        ("domotz_devices_uptime", {"agent_id": 7, "device_id": 9}, "agent/7/device/9/uptime"),
        ("domotz_devices_inventory", {"agent_id": 7, "device_id": 9}, "agent/7/device/9/inventory"),
        ("domotz_metrics_variables_list", {"agent_id": 7, "device_id": 9}, "agent/7/device/9/variable"),
        ("domotz_metrics_variable_history", {"agent_id": 7, "device_id": 9, "variable_id": 3}, "agent/7/device/9/variable/3/history"),
        ("domotz_metrics_snmp_sensors_list", {"agent_id": 7, "device_id": 9}, "agent/7/device/9/eye/snmp"),
        ("domotz_metrics_sensor_history", {"agent_id": 7, "device_id": 9, "sensor_id": 4}, "agent/7/device/9/eye/snmp/4/history"),
        ("domotz_network_topology", {"agent_id": 7}, "agent/7/network-topology"),
        ("domotz_network_interfaces", {"agent_id": 7}, "agent/7/network/interfaces"),
        ("domotz_network_ip_conflicts", {"agent_id": 7}, "agent/7/ip-conflict"),
        ("domotz_alerts_profiles_list", {}, "alert-profile"),
        ("domotz_power_outlets_list", {"agent_id": 7, "device_id": 9}, "agent/7/device/9/power-outlet"),
    ],
)
async def test_documented_paths(monkeypatch, tool, args, path):
    rec = Recorder()
    await _call(monkeypatch, rec, tool, args)
    assert rec.calls(path, "GET"), [r.url.path for r in rec.requests]


async def test_device_alert_bindings_are_filtered_to_the_device(monkeypatch):
    rec = Recorder({"alert-profile/binding/agent/7/device": [{"alert_profile_id": 1, "device_id": 9}, {"alert_profile_id": 2, "device_id": 10}]})
    result = await _call(monkeypatch, rec, "domotz_alerts_device_list", {"agent_id": 7, "device_id": 9})
    assert result["bindings"] == [{"alert_profile_id": 1, "device_id": 9}]


async def test_outlet_control_requires_confirm(monkeypatch):
    rec = Recorder()
    args = {"agent_id": 7, "device_id": 9, "outlet_id": "3", "action": "off", "confirm": False}
    result = await _call(monkeypatch, rec, "domotz_power_outlet_control", args)
    assert result["sent"] is False
    assert rec.requests == []


async def test_outlet_control_posts_action(monkeypatch):
    rec = Recorder({"POST agent/7/device/9/power-outlet/3/action/cycle": lambda r: httpx.Response(202, content=b"")})
    args = {"agent_id": 7, "device_id": 9, "outlet_id": 3, "action": "cycle", "confirm": True}
    result = await _call(monkeypatch, rec, "domotz_power_outlet_control", args)
    assert rec.calls("agent/7/device/9/power-outlet/3/action/cycle", "POST")
    assert result["sent"] is True and result["outlet_id"] == "3"
