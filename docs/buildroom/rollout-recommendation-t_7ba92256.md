# Hermes Self-Development Rollout Recommendation

**Task:** t_7ba92256
**Date:** 2026-05-11
**Status:** Historical rollout recommendation — superseded by `manual-dry-run-deployment.md`

> **2026-05-11 update:** The three blockers identified in this handoff — protected-surface containment, `buildroom.lock`, and deterministic assignee/idempotency behavior — have since been fixed, tested, reviewed, rebased onto current `origin/main`, and documented in `docs/buildroom/manual-dry-run-deployment.md`. The current approved posture is still manual dry-run only: no cron, no Kanban writes, and no worker dispatch.

---

## What the dry-run self-development loop can do today

The Buildroom contract-chain scaffold is committed to main and working. You can manually trigger it end-to-end:

```
Research vault → subc-handoff.json → handoff adapter (dry-run) → validated artifact room → operator summary
```

Specifically:

- **`handoff.py`** reads a `subc-handoff.json` signal file and produces exactly two artifacts: `research-input` and `idea-contract`. Nothing else. No Kanban writes, no cron, no config touches.
- **`validator.py`** checks artifact order, chain_id/parent_id consistency, trust gates, and delta state. It exposes a `--json` flag for scripting.
- **`summary.py`** produces a redacted operator summary with `sk-*`, `bearer`, and `xai-*` strings scrubbed before human review.
- **24 tests pass.** Demo fixture validates clean (`valid=true, artifact_count=12`).

Smoke-test commands:

```bash
cd /Users/caseymoore/.hermes/hermes-agent

# Validate the demo chain
./venv/bin/python -m hermes_cli.buildroom.validator tests/fixtures/buildroom/demo-chain --json

# Run the test suite
./venv/bin/python -m pytest tests/test_buildroom_adapter.py tests/test_buildroom_validator.py -q

# Dry-run a handoff from a fixture
./venv/bin/python -m hermes_cli.buildroom.handoff \
  --handoff tests/fixtures/buildroom/fixture-handoff/subc-handoff.json \
  --output /tmp/buildroom-dry-run
./venv/bin/python -m hermes_cli.buildroom.validator /tmp/buildroom-dry-run --json
```

---

## What is still manual

| What | Status |
|---|---|
| Triggering `handoff.py` | Manual CLI call only |
| Writing `subc-handoff.json` | Manual (Research vault signals) |
| `intent-review` and `main-review` artifacts | Manual human entry |
| `product-plan`, `build-plan` | Manual |
| Coder/QA/Trust/Retention artifacts | Manual |
| Any Kanban task creation | Blocked — not wired |
| Any cron wiring | Not done |
| `~/.hermes/buildroom.lock` off-switch | Documented but not implemented |

---

## Three blockers before supervised auto-create or cron

The dry-run proposal pilot (t_d9af34e4) confirmed the scaffold is sound, but also flagged safety issues that must be fixed before flipping any switch:

### 1. Protected-surface path checks are fragile
The validator uses basic set-intersection for allowed-path checks. It does not handle tilde expansion (`~`), parent-directory traversal (`../`), or symlink resolution. A crafty `allowed_paths = ["hermes_cli/"]` could currently escape to `~/.hermes/` if a parent reference is involved. Needs containment, normalization, and exact prefix matching.

### 2. Global off-switch not implemented
`~/.hermes/buildroom.lock` is documented as the kill switch in `POLICY.md`, but no adapter checks for it. Before any autonomous dispatch — even a cron that just re-validates — the lock file check must exist and be verified in a test.

### 3. Hardcoded assignee and idempotency keys
Proposed nodes defaulted to `assignee_profile: "coder"` with a timestamp in the idempotency key. Both are footguns: routing everything to coder bypasses risk-aware profile routing, and time-based idempotency keys defeat deduplication. These need to be explicit in `product-plan` before auto-create is on the table.

---

## Exact approval needed

Do not approve supervised auto-create or cron yet. The three blockers above need to be fixed and reviewed first.

**Approval path (after blockers are resolved):**

Approve supervised auto-create only with ALL of these constraints explicitly stated:

> "Approve supervised Buildroom auto-create for Band 0 (docs, comments, type hints) and Band 1 (new plugins, new tools, new optional-skills in isolated files) proposal cards only. No worker dispatch. No Kanban task creation beyond a non-running proposal notification card. No cron creation or changes. Honor `~/.hermes/buildroom.lock` as the global off-switch. Block and alert on any protected-surface hit or risk-band violation."

**Protected surfaces that must never be touched regardless of approval scope:**
- `~/.hermes/config.yaml`, `~/.hermes/.env`, `~/.hermes/auth.json`
- `gateway/platforms/` (existing routes/credentials)
- `hermes_state.py` (database schema)
- Cloudflare tunnel config
- Production trading/broker state
- `/Users/caseymoore/Projects/hermes-trading-cockpit` (HTC product repo)
- Cron jobs

---

## Suggested initial autonomous scope (once blockers are fixed)

**Safe to try after blockers are resolved:**

| Scope | Allowed | Notes |
|---|---|---|
| Docs, comments, type-hint refactors | Yes | Band 0, auto-QA pass + human notification |
| New optional-skills in isolated files | Yes | Band 1, needs QA + Main approval gate |
| New plugins/tools in isolated files | Yes | Band 1, needs QA + Main approval gate |
| Existing logic changes | No | Band 2+, needs mandatory Main-Review |
| Core loop (`run_agent.py`, `agent/`, `gateway/`) | No | Band 3, permanently forbidden for auto-build |
| Kanban task auto-creation | No | Only non-running proposal/notification cards, after explicit Casey approval per-instance |
| Worker dispatch | No | Not in v1 |
| Cron changes | No | Separate explicit approval required |

---

## Rollback/off switch

### Off switch for any future autonomous run

```bash
# Kill all active buildroom adapters immediately
touch ~/.hermes/buildroom.lock

# Verify it's in effect
cat ~/.hermes/buildroom.lock
```

The lock file must be checked by the adapter before any write operation. If you flip this, everything stops.

### Rollback for this dry-run

No rollback needed for completed runs — no production state was changed. To remove artifacts from the proposal pilot:

```bash
rm -rf /Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_d9af34e4
rm -f /Users/caseymoore/.hermes/hermes-agent/docs/buildroom/proposal-receipt-t_d9af34e4.md
```

To remove the entire buildroom scaffold if you ever want a clean slate:

```bash
rm -rf /Users/caseymoore/.hermes/hermes-agent/hermes_cli/buildroom/
rm -f /Users/caseymoore/.hermes/hermes-agent/tests/test_buildroom_adapter.py
rm -f /Users/caseymoore/.hermes/hermes-agent/tests/test_buildroom_validator.py
rm -rf /Users/caseymoore/.hermes/hermes-agent/tests/fixtures/buildroom/
rm -f /Users/caseymoore/.hermes/hermes-agent/docs/buildroom/proposal-receipt-t_d9af34e4.md
rm -f /Users/caseymoore/.hermes/hermes-agent/docs/buildroom/handoff-t_fad4d33d.md
rm -f /Users/caseymoore/.hermes/hermes-agent/docs/buildroom/rollout-recommendation-t_7ba92256.md
# keep: spec.md, contract-schemas.md, POLICY.md, ops-receipt-t_42f3c83b.md
```

### How to inspect receipts

All completed buildroom runs produce a timestamped receipt directory:

```bash
# List all buildroom receipts
ls -d /Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/*/proposal-*/

# Inspect a specific receipt
cat /Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_d9af34e4/proposal-20260511T054252Z/summary.json
cat /Users/caseymoore/.hermes/hermes-agent/docs/buildroom/proposal-receipt-t_d9af34e4.md
```

Each receipt includes pre/post state snapshots showing Kanban task counts and cron job hashes — you can confirm nothing moved.

---

## Summary for your decision

**Right now:** The buildroom is a manual scaffold. You can drive it with CLI commands, it produces validated artifacts, and it has touched nothing production. The 24 tests pass and the proposal pilot confirmed zero side effects.

**Do not add cron or supervised auto-create yet.** Three real safety blockers stand between here and that mode. The policy doc (POLICY.md) already defines what "safe" looks like — the code just hasn't gotten there yet.

**Next practical step:** Fix the three blockers (path normalization, `buildroom.lock` implementation, explicit assignee/idempotency in product-plan), get a reviewer to sign off, then come back for explicit Casey approval with the exact wording above.

---

*Writer profile handoff. Parent: t_d9af34e4. This document is the Casey-facing approval input for the self-development rollout decision.*
