# PRD-21260 · Code review

## Round 1 · 2026-10-30 · reviewed dev/PRD-21260 @ 8fb5c09 (base main @ c5df7fd)

Status: frozen @ 8fb5c09

Verdict: approved

### Scope

Single-repo MCP ticket (`Track: vendor-mcp`, release order: any). `dev/PRD-21260` is already in
sync with `main` (merge-base `c5df7fd` == `origin/main` HEAD, 0 commits to sync). Diff reviewed:
`git diff origin/main...HEAD` (3 commits: design docs, `feat(alerts)` implementation, Self-test/Handoff
docs), 10 files changed, 749 insertions / 13 deletions.

### Verification performed

- Re-ran the repo's own gate on the tested commit `8fb5c09` (`uv sync && uv run pytest -q`):
  `244 passed, 1 warning in 8.29s` — matches the `[DEV]` stub's claim exactly (same count, same
  pre-existing unrelated `StarletteDeprecationWarning`).
- `grep -rnP '[\x{4e00}-\x{9fff}]' --exclude-dir=.git --exclude-dir=.venv .` — no output (no
  Chinese characters introduced).
- Read `src/domotz_mcp/api_client.py` `request()` to confirm the new `delete()` method goes
  through the same retry/error-classification path as `get`/`post` (DELETE is never retried on
  5xx, only on 429, so an unbind call can't silently fire twice) — no new code path, no gap.
- Read `src/domotz_mcp/tools/_common.py` `run_tool()` to confirm all eight new tools inherit the
  existing error-envelope wrapper, `window()` ISO-8601 validation, and `locate()`/`page_result()`
  paging — no new error-handling code was written for this ticket, so there is no new error path
  to find bugs in.

### Findings

None. (0 must-fix, 0 suggestion.)

Notes supporting the verdict (not findings, just what was checked and held up):

- **Design conformance**: all 8 new tools (`domotz_alerts_list`, `domotz_alerts_resolve`,
  `domotz_alert_rules_list`/`_get`/`_bind_agent`/`_unbind_agent`/`_bind_device`/`_unbind_device`)
  match the Data & API contract table in `docs/tickets/PRD-21260.md` exactly: endpoint, required
  params, and `READ_ONLY`/`ALERT_ACTION` annotation per tool.
- **Confirm-gate correctness**: all five write tools return `{"sent": false, ...}` without calling
  `client.post`/`client.delete` when `confirm` is not `True`, and call Domotz only when it is —
  verified both by reading the code and by the passing `test_*_requires_confirm` /
  `test_*_sends_when_confirmed` tests in `tests/test_api_client.py`.
- **Regression**: `WRITE_TOOLS`/`DESTRUCTIVE_TOOLS` split in `tests/test_tools.py` is a correct,
  minimal fix for the fact that `test_annotations_match_side_effects` previously conflated "is a
  write" with "is destructive" (true only by accident, since `domotz_power_outlet_control` was the
  only write tool before this ticket) — `domotz_power_outlet_control` stays the only
  `destructiveHint=True` tool, so its own behavior/test outcome is unchanged. This is a legitimate
  tech-design-level adjustment (annotation value, not user-visible behavior), documented in the
  "Deviation from the tech design" section as required.
- **No new dependency, no new module, no reshaping of existing tools** — matches "Reuse & cleanup".
  The two legacy `domotz_alerts_profiles_list`/`domotz_alerts_device_list` tools are untouched, and
  `tests/contract_types.json` correctly has no new entries (new tools have no prior-version
  contract to keep).
- **TC4b** (live `domotz_alerts_resolve` round trip) is `untested` with a documented reason (no
  vendor test account) — per `references/mcp-track.md` §2.5 this does not block the ticket and is
  not a must-fix.
- No schema/migration concerns (MCP repo, no database). No UI concerns (MCP repo, no interface).

### Fixes

N/A — round 1, approved with no must-fix.
