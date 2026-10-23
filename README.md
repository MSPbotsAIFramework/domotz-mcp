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

<div align="center">

## MSPbots Connector

**The MCP Gateway built for MSPs: visible, controlled, and your data stays where it belongs.**

[**Get started at connect.mspbots.ai →**](https://connect.mspbots.ai)

</div>

---

MSPbots Connector gives your AI clients one MCP URL to reach your entire MSP stack (RMM, PSA, documentation, security, finance), and gives you control over who can call which tool and a record of everything that was called.

**Hosted service: [connect.mspbots.ai](https://connect.mspbots.ai)** · Free to use.

### Why Connector

![MSPbots Connector](https://stgoss.mspbots.ai/files/mcp/mspbots-mcp.png)

| | |
|---|---|
| **Visible** | Every tool call is logged: who, which vendor, when. Usage dashboard, CSV export, SIEM streaming. |
| **Controlled** | Role-based, per-tool allowlist. Deny by default. |
| **Protected** | Credentials encrypted per record. AI clients never see your vendor passwords or tokens. |
| **MSP-native** | Built for the MSP stack only: RMM, PSA, documentation, security, finance. |

### Quick start

1. **Sign up** at [connect.mspbots.ai](https://connect.mspbots.ai).
2. **Connect your vendors.** Pick from 150+ connectors and authorize each one on the vendor's own page, or bring your own API keys. No extra vendor accounts needed.
3. **Set access.** Create roles and decide which tools each role may call. Nothing is allowed until you allow it.
4. **Add your MCP URL to your AI client.** Copy the URL from your Connector dashboard into Claude, ChatGPT, Cursor, VS Code, Gemini, Codex, or any MCP-capable client.
5. **Ask your AI to do real work**, and watch every call appear in the audit log.

### Features

**Unified gateway**
- One MCP URL for all your AI clients
- 150+ connectors across the MSP stack
- Custom MCP servers supported, free
- Authorization happens on each vendor's own page; the AI never sees passwords or tokens
- Bring your own credentials: use the vendor API keys you already have
- Multiple accounts per app; connect once, reuse across AI clients
- Tool search: finds the right action for the task
- One sign-in; vendor credentials are injected behind the scenes and OAuth tokens refresh automatically

**Visibility**
- Audit log for every tool call (who, which vendor, when)
- Usage dashboard: call volume, top vendors, error rate, per-user activity
- Export audit logs to CSV, or stream to Loki, Graylog, or LogScale (SIEM)
- Optional recording of tool arguments and result summaries (off by default, enabled per organization)

**Control**
- Per-role, per-tool allowlist, deny by default
- owner / admin / member roles
- SCIM provisioning with Entra ID, Okta, JumpCloud, and Google Workspace

**Security**
- Credentials encrypted one record at a time (AES-256-GCM, per-record key)
- AI clients authenticate with OAuth 2.1 + PKCE
- Vendor responses are scanned for prompt-injection patterns and returned as structured data. This is one layer of defense, not a guarantee against every attack.
- Static egress IP for customer firewall and API allowlisting

### Pricing

**Free.**

Links: [connect.mspbots.ai](https://connect.mspbots.ai) · [mspbots.ai](https://mspbots.ai)

---

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

A request to `/mcp` without the key gets HTTP 401; an unknown region does not block the request, and tools return `invalid_argument` instead.

## Tools

All tools return a JSON string. `agent_id` comes from `domotz_agents_list` and `device_id` from
`domotz_devices_list`. History tools take an optional ISO 8601 window (`from_time`, `to_time`).
The two paged lists also take `offset` (a 0-based record position that overrides `page_number`)
and return `has_more`, `offset` and `next_offset`: pass `next_offset` to continue, because when a
page is cut to fit the response size limit the rest of it is on no other page number.

| Tool | Purpose | Parameters (required in **bold**) |
|---|---|---|
| `domotz_navigate` | Describe the tools of one area (changes nothing) | **domain** (`agents`, `devices`, `metrics`, `network`, `alerts`, `power`) |
| `domotz_back` | List every area and its tools (changes nothing) | - |
| `domotz_status` | Connection check and the key's API call usage and limits | - |
| `domotz_agents_list` | Collectors (one per site): status, IP, location, licence | display_name, page_size, page_number, offset |
| `domotz_agents_get` | One collector's details | **agent_id** |
| `domotz_devices_list` | Devices on a collector's network, with counts by status | **agent_id**, show_hidden, show_excluded |
| `domotz_devices_get` | One device: vendor, model, OS, IP / MAC, status, importance | **agent_id**, **device_id** |
| `domotz_devices_uptime` | A device's uptime over a window | **agent_id**, **device_id**, from_time, to_time |
| `domotz_devices_history` | A device's state-change (online / offline / down) events | **agent_id**, **device_id**, from_time, to_time |
| `domotz_devices_inventory` | A device's inventory fields (owner, location, notes, ...) | **agent_id**, **device_id** |
| `domotz_metrics_variables_list` | A device's monitored variables with current values | **agent_id**, **device_id**, page_size, page_number, has_history, offset |
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
