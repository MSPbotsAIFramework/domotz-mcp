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
"""Shared argument types, time-window helper and the error-handling wrapper."""

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from mcp.types import ToolAnnotations
from pydantic import Field

from .._json import dump_json_capped, error_envelope
from ..api_client import DomotzClient, DomotzError

logger = logging.getLogger("domotz_mcp.tools")

ClientFactory = Callable[[], DomotzClient | None]

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True)
LOCAL = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
# Switching an outlet cuts or restores power to whatever is plugged in.
POWER_ACTION = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True)

NOT_CONFIGURED = error_envelope(
    "not_configured", "Domotz credentials are missing for this request (X-Domotz-API-Key).", False
)

AgentId = Annotated[int, Field(description="Collector (agent) id from domotz_agents_list.", ge=1)]
DeviceId = Annotated[int, Field(description="Device id from domotz_devices_list.", ge=1)]
From = Annotated[str | None, Field(description="Window start, ISO 8601 (e.g. 2026-06-01T00:00:00Z).")]
To = Annotated[str | None, Field(description="Window end, ISO 8601 (default now).")]

Offset = Annotated[
    int | None,
    Field(description="Record position to start from (0-based, overrides page_number); pass next_offset from the previous result.", ge=0),
]

# Domotz's page size when a request names none (its list endpoints default to 100 per page).
API_DEFAULT_PAGE_SIZE = 100


def locate(offset: int | None, page_number: int | None, page_size: int | None) -> tuple[dict[str, int | None], int, int, int]:
    """(paging params, page_number, page_size, start) for a read from record ``start``.

    Domotz pages by number only (from 0), so a position is reached by asking for the page that
    holds it (same page size) and skipping the records before it. Without offset the request
    carries page_number / page_size exactly as given, as before.
    """
    size = page_size or API_DEFAULT_PAGE_SIZE
    if offset is None:
        number = page_number or 0
        return {"page_size": page_size, "page_number": page_number}, number, size, number * size
    number = offset // size
    return {"page_size": size, "page_number": number}, number, size, offset


def page_result(key: str, payload: Any, number: int, size: int, start: int) -> dict:
    """Records from ``start`` of page ``number``: {<key>, count, page_number, page_size, has_more, offset, next_offset}.

    next_offset continues right after the last record returned, also when the result is cut to
    fit the size limit (a page number cannot: the rest of a cut page is on no other page).
    """
    rows = payload if isinstance(payload, list) else []
    more = len(rows) >= size
    items = rows[start - number * size :]
    return {
        key: items,
        "count": len(items),
        "page_number": number,
        "page_size": size,
        "has_more": more,
        "offset": start,
        "next_offset": start + len(items) if more else None,
        "_resume": {"key": "next_offset", "start": start},
    }


def window(start: str | None, end: str | None) -> dict[str, str | None]:
    """Validate an optional ISO 8601 from / to pair and return Domotz query params."""
    parsed: dict[str, datetime | None] = {}
    for name, value in (("from", start), ("to", end)):
        text = (value or "").strip()
        if not text:
            parsed[name] = None
            continue
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f'{name}_time must be an ISO 8601 date-time, e.g. "2026-06-01T00:00:00Z" (got "{value}").') from e
        parsed[name] = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    if parsed["from"] and parsed["to"] and parsed["to"] < parsed["from"]:
        raise ValueError("to_time must be after from_time.")
    return {k: v.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if v else None for k, v in parsed.items()}


async def run_tool(
    name: str,
    client_factory: ClientFactory,
    action: Callable[[DomotzClient], Awaitable[Any]],
) -> str:
    """Resolve the caller's client, run ``action``, and always return a string.

    Errors never escape as exceptions: they become the standard error envelope.
    """
    client = client_factory()
    if client is None:
        return NOT_CONFIGURED
    if client.header_error:
        return error_envelope("invalid_argument", client.header_error, False)
    started = time.monotonic()
    try:
        result = await action(client)
    except DomotzError as e:
        logger.info("tool=%s outcome=error status=%s ms=%d", name, e.status_code, _ms(started))
        return e.to_envelope()
    except ValueError as e:
        logger.info("tool=%s outcome=invalid_argument ms=%d", name, _ms(started))
        return error_envelope("invalid_argument", str(e), False)
    except Exception as e:  # noqa: BLE001 - tools must never raise
        logger.warning("tool=%s outcome=unexpected error=%s ms=%d", name, type(e).__name__, _ms(started))
        return error_envelope("upstream_error", f"Unexpected error: {type(e).__name__}", True)
    logger.info("tool=%s outcome=ok ms=%d", name, _ms(started))
    if result is None:
        result = {"result": None, "note": "Domotz returned an empty response."}
    return result if isinstance(result, str) else dump_json_capped(result)


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
