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
"""Credential middleware: 401 on a missing key, deferred header errors, region resolution, isolation."""

import asyncio

import pytest
from starlette.testclient import TestClient

from domotz_mcp.__main__ import build_http_app
from domotz_mcp.server import (
    GatewayCredentialsMiddleware,
    _credentials_var,
    create_mcp_server,
    get_client_from_context,
    resolve_base_url,
)

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
LIST_TOOLS = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
US = "https://api-us-east-1-cell-1.domotz.com/public-api/v1"
EU = "https://api-eu-west-1-cell-1.domotz.com/public-api/v1"


def _client() -> TestClient:
    return TestClient(build_http_app(create_mcp_server()))


def test_health_is_local():
    with _client() as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.parametrize("value", [None, "", "${DOMOTZ_API_KEY}"])
def test_missing_key_returns_401(value):
    headers = dict(MCP_HEADERS)
    if value is not None:
        headers["X-Domotz-API-Key"] = value
    with _client() as client:
        resp = client.post("/mcp", json=LIST_TOOLS, headers=headers)
    assert resp.status_code == 401
    assert resp.json()["required_headers"] == ["X-Domotz-API-Key"]


@pytest.mark.parametrize("region", ["mars", "https://evil.example.com/public-api/v1", "http://api-us-east-1-cell-1.domotz.com"])
def test_bad_region_is_reported_by_tools(region):
    call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "domotz_status", "arguments": {}}}
    with _client() as client:
        resp = client.post("/mcp", json=call, headers=MCP_HEADERS | {"X-Domotz-API-Key": "k", "X-Domotz-Region": region})
    assert resp.status_code == 200
    assert '\\"invalid_argument\\"' in resp.text and "X-Domotz-Region must be us, eu" in resp.text


def test_placeholder_headers_still_list_tools():
    # The admin console refreshes the tool catalog with placeholder header values.
    headers = {"X-Domotz-API-Key": "placeholder", "X-Domotz-Region": "placeholder"}
    with _client() as client:
        resp = client.post("/mcp", json=LIST_TOOLS, headers=MCP_HEADERS | headers)
    assert resp.status_code == 200
    assert "domotz_devices_list" in resp.text


@pytest.mark.parametrize(
    "region,expected",
    [
        (None, US),
        ("us", US),
        ("US-East-1", US),
        ("eu", EU),
        ("eu-west-1", EU),
        ("https://api-eu-west-1-cell-1.domotz.com/public-api/v1/", EU),
        ("https://api-eu-west-1-cell-1.domotz.com", EU),
        ("ap", None),
    ],
)
def test_resolve_base_url(region, expected):
    assert resolve_base_url(region) == expected


def test_tools_list_over_http():
    with _client() as client:
        resp = client.post("/mcp", json=LIST_TOOLS, headers=MCP_HEADERS | {"X-Domotz-API-Key": "k"})
    assert resp.status_code == 200
    for name in ("domotz_navigate", "domotz_devices_list", "domotz_power_outlet_control"):
        assert name in resp.text


def _run_middleware(headers: list[tuple[bytes, bytes]]) -> dict:
    seen: dict = {}

    async def app(scope, receive, send):
        seen["credentials"] = _credentials_var.get()
        seen["client"] = get_client_from_context()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(_message):
        return None

    asyncio.run(GatewayCredentialsMiddleware(app)({"type": "http", "path": "/mcp", "headers": headers}, receive, send))
    return seen


def test_key_and_region_reach_request_context_and_are_reset():
    seen = _run_middleware([(b"x-domotz-api-key", b" key-123 "), (b"x-domotz-region", b"eu")])
    assert seen["credentials"].api_key == "key-123"
    assert seen["client"].base_url == EU
    assert seen["client"].header_error is None
    assert _credentials_var.get() is None


def test_bad_region_falls_back_to_default_endpoint():
    seen = _run_middleware([(b"x-domotz-api-key", b"key-123"), (b"x-domotz-region", b"mars")])
    assert seen["client"].base_url == US
    assert "X-Domotz-Region must be" in seen["client"].header_error


def test_concurrent_requests_do_not_share_credentials():
    observed: list[tuple[str, str]] = []

    async def app(scope, receive, send):
        before = _credentials_var.get().api_key
        await asyncio.sleep(0.01)
        observed.append((before, _credentials_var.get().api_key))
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(_message):
        return None

    middleware = GatewayCredentialsMiddleware(app)

    def scope(key: bytes) -> dict:
        return {"type": "http", "path": "/mcp", "headers": [(b"x-domotz-api-key", key)]}

    async def both():
        await asyncio.gather(middleware(scope(b"tenant-a"), receive, send), middleware(scope(b"tenant-b"), receive, send))

    asyncio.run(both())
    assert sorted(observed) == [("tenant-a", "tenant-a"), ("tenant-b", "tenant-b")]


def test_credentials_repr_hides_key():
    seen = _run_middleware([(b"x-domotz-api-key", b"very-secret-key")])
    assert "very-secret-key" not in repr(seen["credentials"])
