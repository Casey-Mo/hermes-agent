# Hermes Buildroom v1 — Operator Handoff

**Task:** t_fad4d33d
**Scope:** Hermes-wide self-development infrastructure. **Not HTC board execution.**
**Date:** 2026-05-11

---

## What was built

The buildroom is a contract-chain scaffold for existing Hermes profiles to pass structured JSON artifacts to each other before any adapter does work. The full pipeline runs Research → Subc → Main → Analyst → Coder → QA → Trust → Retention.

Files committed:

```
hermes_cli/buildroom/__init__.py
hermes_cli/buildroom/schemas.py      # Pydantic envelopes, REQUIRED_ARTIFACT_ORDER, cross-check rules
hermes_cli/buildroom/handoff.py     # research→subc adapter, dry-run only, produces 2 artifacts max
hermes_cli/buildroom/validator.py   # room validator, checks order/chain_id/parent_id/trust-gates/delta-state
hermes_cli/buildroom/summary.py     # redacted operator summary, secret scrubbing (sk-*, bearer, etc.)
tests/test_buildroom_adapter.py     # adapter unit tests
tests/test_buildroom_validator.py   # validator unit tests
tests/fixtures/buildroom/demo-chain/    # 12-artifact sanitized demo chain (demo-buildroom-0)
tests/fixtures/buildroom/fixture-handoff/subc-handoff.json  # fixture input
docs/buildroom/spec.md              # pipeline diagram, step-by-step, safety gates, off-switch
docs/buildroom/contract-schemas.md # schema docs, validation rules, usage commands
docs/buildroom/ops-receipt-t_42f3c83b.md  # parent task ops pilot receipt
```

Commits on this work:

```
1881c0d47 docs(buildroom): add local ops pilot receipt
bfdb2cc64 fix(buildroom): close trust gates and bearer redaction
29593a02d feat(buildroom): research-to-subc handoff adapter (dry-run only)
a0f744b67 feat: add buildroom contract scaffold
```

---

## Review verdicts

All 24 targeted tests passed:

```
./venv/bin/python -m pytest tests/test_buildroom_adapter.py \
  tests/test_buildroom_validator.py tests/hermes_cli/test_status_redaction.py -q
# 24 passed in 1.44s
```

Demo fixture validation: `valid=true, artifact_count=12, errors=[]`

Runtime pilot validation (sanitized local run): `valid=true, artifact_count=12, errors=[]`

Git diff check: clean — no uncommitted whitespace or error-state files.

Secret scan on receipt + runtime manifest + operator summary: `secret_scan=pass`

---

## Smoke-test commands

Validate the demo chain any time:

```bash
cd /Users/caseymoore/.hermes/hermes-agent
./venv/bin/python -m hermes_cli.buildroom.validator tests/fixtures/buildroom/demo-chain --json
```

Run the full buildroom test suite:

```bash
./venv/bin/python -m pytest tests/test_buildroom_adapter.py tests/test_buildroom_validator.py -q
```

Dry-run a handoff from a fixture:

```bash
./venv/bin/python -m hermes_cli.buildroom.handoff \
  --handoff tests/fixtures/buildroom/fixture-handoff/subc-handoff.json \
  --output /tmp/buildroom-dry-run
# prints room path to stdout
./venv/bin/python -m hermes_cli.buildroom.validator /tmp/buildroom-dry-run --json
```

Inspect the runtime pilot from the ops receipt:

```bash
cat /Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_42f3c83b/pilot-20260511T043414Z/runtime-manifest.json
cat /Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_42f3c83b/pilot-20260511T043414Z/operator-summary.json
ls /Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_42f3c83b/pilot-20260511T043414Z/dry-run-ops-pilot-20260511T043414Z/
```

---

## How the buildroom works

1. Research writes signals to `queue/subc-handoff.json` in its vault.
2. Subc/Dreamer picks those up and walks the signals through its signal-state system.
3. The handoff adapter (`hermes_cli.buildroom.handoff`) reads `subc-handoff.json` and creates a dry-run room with exactly two artifacts: `research-input` and `idea-contract`. No approval artifacts, no Kanban tasks, no cron jobs, no config touches.
4. A human (or Main profile) reviews the idea-contract and writes `intent-review` and `main-review` to approve, reject, or narrow scope.
5. If approved: Analyst → `product-plan` (bounded with allowed_paths, non_goals, risks, protected_surfaces), Coder → `build-plan` + `verification`, QA → `qa-verification` + `verification-delta`, Trust → `trust-report`, Retention → `retention-review`, Analyst → `operator-summary`.

v1 is entirely manual. Nothing runs on a schedule. Nothing creates tasks automatically.

---

## What remains before any cron or dashboard automation

The pipeline is proven end-to-end in sanitized dry-run. Before any automation runs, these need to be in place:

| Gap | Status | What needs to happen |
|---|---|---|
| Full autonomous routing | Out of scope for v1 | Separate human approval + review + rollback plan required |
| Kanban task auto-creation | Blocked by design | Only allowed after explicit human approval in a later task |
| Cron wiring | Not done, not wired | Requires policy doc (t_6e86473f) defining risk bands + phase gates |
| Dashboard buildroom view | Not present | No plugin wiring; needs a separate task |
| Production runtime handoff | Not wired | Adapter generates first 2 artifacts only; downstream are fixture placeholders |
| Trust gate enforcement in adapter | Not implemented | Currently enforced by manual review + validator; autonomous enforcement needs design |

Child task t_6e86473f (analyst profile, **not** assigned to this writer) is already queued to design the safe autonomous build gate policy — signal thresholds, risk bands, phase gates (proposal-only → dry-run → supervised auto-build → limited autonomous), and what can vs. cannot be auto-created as Kanban tasks.

---

## Next-step recommendation

**Keep v1 manual. Add a dashboard view as a follow-up task. Do not add a no-agent dry-run cron yet.**

Here's the honest read: the ops pilot passed cleanly — 24 tests, runtime validator, secret scan all green. But the gap list above is real. The buildroom as shipped is a scaffold you can drive manually. It is not yet a system that can run safely on a schedule without someone in the loop.

The right next move is the policy work already queued in t_6e86473f. That task defines the risk bands, phase gates, and exact artifact requirements before autonomous dispatch is even on the table. Without that policy, any cron — even one that just re-validates existing rooms — carries the risk of expanding scope without visibility.

A dashboard view is the lower-risk next step: it gives you read-only visibility into buildroom rooms without changing any execution semantics. It's also the path through which future human approval decisions surface naturally.

---

## Safety invariants confirmed

- No cron jobs created.
- No autonomous dispatch wired.
- No `~/.hermes/config.yaml` edits.
- No gateway, Cloudflare, broker, trading, or HTC repository edits.
- Runtime used sanitized fixtures only — no real tokens, no production auth, no runtime profile state.
- Adapter constrained to producing only `research-input` and `idea-contract`; enforced by the test suite.

---

## Cleanup

Runtime pilot directory (safe to delete, already stale per parent receipt):

```bash
rm -rf /Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_42f3c83b
```

Full rollback — remove all buildroom code and docs if needed:

```bash
rm -rf hermes_cli/buildroom/ tests/test_buildroom_adapter.py tests/test_buildroom_validator.py tests/fixtures/buildroom/ docs/buildroom/
```

No production off-switch needed — nothing production was wired.

---

## Scope confirmation

**This is Hermes Agent self-development / buildroom infrastructure. This is not HTC product work.**

The buildroom operates on the Hermes codebase at `/Users/caseymoore/.hermes/hermes-agent`. The HTC repository at `/Users/caseymoore/Projects/hermes-trading-cockpit` was not touched and is not involved. The kanban board confirms this is Hermes-wide, not HTC board execution.

---

*Writer profile handoff complete. Child task t_6e86473f (policy design) is queued for the analyst profile and unblocks further automation decisions.*