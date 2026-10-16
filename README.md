# Domotz MCP Server

An [MCP](https://modelcontextprotocol.io) server for the [Domotz](https://www.domotz.com) Public
API (v1), the network monitoring platform MSPs run on client sites. It lets an AI agent read
collectors and the devices they discover, device uptime and state-change history, inventory
fields, variables and SNMP sensors with their history, network topology, monitored networks,
IP conflicts, alert profiles and smart power outlets and, on explicit request, switch an outlet.

- Transport: MCP Streamable HTTP at `POST /mcp`, health probe at `GET /health`
- Stateless and multi-tenant: the key arrives on every request as an HTTP header and is never
  stored; every tool is listed from the first `tools/list`
- Python 3.12, [uv](https://docs.astral.sh/uv/), FastMCP, httpx
- License: Apache-2.0, Copyright 2026 MSPbots.ai

## Authentication headers

| Header | Required | Type | Default | Allowed values | Description | Example |
|---|---|---|---|---|---|---|
| `X-Domotz-API-Key` | Yes | string | none | - | Domotz Public API key | `your-api-key` |
| `X-Domotz-Region` | No | string | `us-east-1` | `us`, `us-east-1`, `eu`, `eu-west-1`, or the https API endpoint shown in the portal | Domotz cell that hosts the account | `us` |

Where to get them: in the Domotz portal open **Settings -> Services -> API Keys** and create a
key with full access (an "Agent Activation only" key cannot read data). The same page shows
the account's API endpoint, for example `https://api-us-east-1-cell-1.domotz.com/public-api/v1`;
pass it, or its region, as `X-Domotz-Region`.

How the key is sent to Domotz: every call goes to
`https://api-{region}-cell-1.domotz.com/public-api/v1/...` with the key in the `X-Api-Key`
header. An endpoint URL is accepted only over https on a `domotz.com` host.

A request to `/mcp` without the key gets HTTP 401; an unknown region gets HTTP 400.

## Tools

All tools return a JSON string. `agent_id` comes from `domotz_agents_list` and `device_id` from
`domotz_devices_list`. History tools take an optional ISO 8601 window (`from_time`, `to_time`).

| Tool | Purpose | Parameters (required in **bold**) |
|---|---|---|
| `domotz_navigate` | Describe the tools of one area (changes nothing) | **domain** (`agents`, `devices`, `metrics`, `network`, `alerts`, `power`) |
| `domotz_back` | List every area and its tools (changes nothing) | - |
| `domotz_status` | Connection check and the key's API call usage and limits | - |
| `domotz_agents_list` | Collectors (one per site): status, IP, location, licence | display_name, page_size, page_number |
| `domotz_agents_get` | One collector's details | **agent_id** |
| `domotz_devices_list` | Devices on a collector's network, with counts by status | **agent_id**, show_hidden, show_excluded |
| `domotz_devices_get` | One device: vendor, model, OS, IP / MAC, status, importance | **agent_id**, **device_id** |
| `domotz_devices_uptime` | A device's uptime over a window | **agent_id**, **device_id**, from_time, to_time |
| `domotz_devices_history` | A device's state-change (online / offline / down) events | **agent_id**, **device_id**, from_time, to_time |
| `domotz_devices_inventory` | A device's inventory fields (owner, location, notes, ...) | **agent_id**, **device_id** |
| `domotz_metrics_variables_list` | A device's monitored variables with current values | **agent_id**, **device_id**, page_size, page_number, has_history |
| `domotz_metrics_variable_history` | Value history of one variable | **agent_id**, **device_id**, **variable_id**, from_time, to_time |
| `domotz_metrics_snmp_sensors_list` | Custom SNMP sensors configured on a device | **agent_id**, **device_id** |
| `domotz_metrics_sensor_history` | Value history of one SNMP sensor | **agent_id**, **device_id**, **sensor_id**, from_time, to_time |
| `domotz_network_topology` | Site topology: which devices connect where | **agent_id** |
| `domotz_network_interfaces` | Networks (interfaces / subnets) a collector monitors | **agent_id** |
| `domotz_network_ip_conflicts` | Active IP address conflicts | **agent_id** |
| `domotz_alerts_profiles_list` | Alert profiles of the account | - |
| `domotz_alerts_device_list` | Alert profiles bound to one device | **agent_id**, **device_id** |
| `domotz_power_outlets_list` | A PDU's / smart plug's outlets and power state | **agent_id**, **device_id** |
| `domotz_power_outlet_control` | Switch an outlet on, off or power-cycle it (**write**) | **agent_id**, **device_id**, **outlet_id**, **action** (`on`, `off`, `cycle`), **confirm** |

Errors come back as a JSON envelope instead of an exception:

```json
{"error": {"code": "unauthorized", "message": "Domotz returned HTTP 401 for agent: ...", "retryable": false}}
```

`code` is one of `not_configured`, `unauthorized`, `not_found`, `invalid_argument`,
`rate_limited`, `upstream_error`. Reads are retried with backoff on 429, 5xx and network
errors; the outlet action is retried only on 429. Domotz limits API calls per day according to
the plan; `domotz_status` shows the current usage.

## Run locally

```bash
uv sync
uv run python -m domotz_mcp          # listens on 0.0.0.0:8080
```

or with Docker:

```bash
docker build --platform linux/amd64 -t domotz-mcp:dev .
docker run --rm -p 8080:8080 domotz-mcp:dev
```

Configuration (environment variables, all optional): `MCP_HTTP_HOST` (default `0.0.0.0`),
`MCP_HTTP_PORT` (default `8080`), `LOG_LEVEL` (default `INFO`). The key is never read from the
environment.

## Testing example

```bash
# list tools
curl -s http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Domotz-API-Key: your-api-key" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# collectors of an EU account
curl -s http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Domotz-API-Key: your-api-key" \
  -H "X-Domotz-Region: eu" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"domotz_agents_list","arguments":{}}}'
```

Unit tests (no network access needed):

```bash
uv run pytest
```

## Delivery notes

- **All tools always listed.** Older versions only listed navigation tools until one was
  called. Behind a stateless gateway that hid every other tool, so this version lists all 21
  tools up front. `domotz_navigate` and `domotz_back` remain for compatibility and only
  describe the tools.
- **Built on the documented endpoints.** `domotz_alerts_device_list` used a route that is not in
  the Domotz OpenAPI definition; it now reads the collector's device bindings
  (`/alert-profile/binding/agent/{agent_id}/device`) and keeps the requested device.
  `domotz_devices_history` now returns state-change events
  (`/history/network/event`), which is what its description promised, instead of round-trip
  delay statistics.
- **Region.** `us` / `eu` and the cell names map to the two public cells (`us-east-1`,
  `eu-west-1`); older versions turned `us` into a host that does not exist.
- **Outlet control.** `domotz_power_outlet_control` still requires `confirm: true` and returns a
  "not sent" result without it.
- **New optional parameters.** History tools gained `from_time` / `to_time`; list tools gained
  the paging and filter options the API offers.

## License

Apache License 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE).
