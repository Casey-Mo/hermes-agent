# Buildroom Manual Dry-Run Deployment Runbook

**Status:** ready for local manual dry-run deployment only
**Updated:** 2026-05-11T06:40:44Z
**Branch:** `casey/buildroom-safety` on `Casey-Mo/hermes-agent`
**Workspace:** `/Users/caseymoore/.hermes/hermes-agent`

This runbook is the current operator reference for deploying the Buildroom contract chain in Casey's Hermes Agent setup. It supersedes the older rollout notes that identified the original three blockers; those blockers have been fixed and independently reviewed, but this still does **not** authorize cron, Kanban writes, or worker dispatch.

## Current deployment posture

| Capability | Status |
|---|---|
| Manual fixture validation | Ready |
| Manual `subc-handoff.json` intake | Ready for pilot |
| Manual proposal dry-run | Ready |
| Protected-surface containment checks | Implemented and tested |
| `$HERMES_HOME/buildroom.lock` / `~/.hermes/buildroom.lock` off-switch | Implemented and tested |
| Deterministic proposal idempotency key | Implemented and tested |
| Real Kanban assignee profile mapping | Implemented for proposal output (`builder`) |
| Automatic Kanban task creation | Not implemented / not approved |
| Automatic worker dispatch | Forbidden in v1 |
| Cron-triggered Buildroom processing | Not wired / not approved |
| Autonomous build | Not approved |

## Allowed mode

The only approved deployment mode right now is:

```text
Research/Subc handoff file
→ manual handoff adapter invocation
→ local Buildroom room artifacts
→ manual validator invocation
→ manual proposal dry-run
→ human/operator review of JSON/Markdown receipts
```

The manual dry-run path must not create Kanban rows, dispatch workers, create or edit cron jobs, edit gateway/platform config, touch Cloudflare config, touch secrets/auth files, or modify the HTC product repository.

## Explicitly forbidden until a separate approval cycle

- no `hermes cron create` or cron-job tool wiring for Buildroom;
- no auto-create of Kanban implementation cards;
- no task status mutation from Buildroom code;
- no dispatcher calls from Buildroom code;
- no writes to protected surfaces;
- no worker execution based only on proposal output;
- no trading/broker/HTC product repo changes;
- no “silent success” claims without saved receipts and reproduced validation.

## Off switch

Create the lock file before experimenting if you want Buildroom disabled globally:

```bash
touch ~/.hermes/buildroom.lock
```

Verify proposal paths block under a lock:

```bash
cd /Users/caseymoore/.hermes/hermes-agent
./venv/bin/python -m hermes_cli.buildroom.proposal \
  tests/fixtures/buildroom/demo-chain \
  --format json
```

Expected locked behavior: the command exits non-zero, JSON status is `blocked`, `approved` is `false`, and the `reason` points at the active `buildroom.lock` file.

Remove the lock only when intentionally running manual dry-run commands:

```bash
rm -f ~/.hermes/buildroom.lock
```

## Baseline verification before a manual pilot

Run from the Hermes Agent checkout:

```bash
cd /Users/caseymoore/.hermes/hermes-agent

./venv/bin/python -m pytest \
  tests/test_buildroom_adapter.py \
  tests/test_buildroom_validator.py \
  tests/test_buildroom_safety.py \
  tests/test_buildroom_proposal.py \
  tests/hermes_cli/test_status_redaction.py \
  -q

./venv/bin/python -m compileall -q hermes_cli/buildroom
./venv/bin/python -m hermes_cli.buildroom.validator tests/fixtures/buildroom/demo-chain --json
./venv/bin/python -m hermes_cli.buildroom.proposal tests/fixtures/buildroom/demo-chain --format json
```

Expected baseline:

- focused tests pass;
- fixture validator returns `valid: true` and `artifact_count: 12`;
- proposal returns `status: dry-run`, `approved: true`, `execute: false`;
- proposed task graph uses real spawnable profiles such as `builder`;
- idempotency key is stable across repeated runs for the same room.

## Manual fixture run

Use this as the deployment smoke before touching real handoffs:

```bash
cd /Users/caseymoore/.hermes/hermes-agent
RUN_ROOT="tmp/buildroom-runtime/manual-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_ROOT"

./venv/bin/python -m hermes_cli.buildroom.validator \
  tests/fixtures/buildroom/demo-chain \
  --json > "$RUN_ROOT/validator.json"

./venv/bin/python -m hermes_cli.buildroom.proposal \
  tests/fixtures/buildroom/demo-chain \
  --format json > "$RUN_ROOT/proposal.json"

./venv/bin/python -m hermes_cli.buildroom.proposal \
  tests/fixtures/buildroom/demo-chain \
  --format markdown > "$RUN_ROOT/proposal.md"
```

Inspect saved receipts before proceeding:

```bash
python3 -m json.tool "$RUN_ROOT/validator.json"
python3 -m json.tool "$RUN_ROOT/proposal.json"
sed -n '1,160p' "$RUN_ROOT/proposal.md"
```

## First real Research/Subc intake pilot

After the baseline fixture run passes, use one real `subc-handoff.json` candidate. Keep the candidate low-risk and preferably docs/tests/operator-visibility only.

```bash
cd /Users/caseymoore/.hermes/hermes-agent
HANDOFF=/path/to/subc-handoff.json
RUN_ROOT="tmp/buildroom-runtime/live-pilot-$(date -u +%Y%m%dT%H%M%SZ)"
ROOM="$RUN_ROOT/room"
mkdir -p "$RUN_ROOT"

./venv/bin/python -m hermes_cli.buildroom.handoff \
  --handoff "$HANDOFF" \
  --output "$ROOM"

./venv/bin/python -m hermes_cli.buildroom.validator \
  "$ROOM" \
  --json > "$RUN_ROOT/validator.json"

./venv/bin/python -m hermes_cli.buildroom.proposal \
  "$ROOM" \
  --format json > "$RUN_ROOT/proposal.json"

./venv/bin/python -m hermes_cli.buildroom.proposal \
  "$ROOM" \
  --format markdown > "$RUN_ROOT/proposal.md"
```

Review gates for the live pilot:

1. Confirm `validator.json` is clean or understand every warning/error.
2. Confirm `proposal.json` has `execute: false`.
3. Confirm risk band is 0 or 1 for the first pilot.
4. Confirm allowed paths do not touch protected surfaces.
5. Confirm no Kanban board state changed.
6. Confirm no cron job state changed.
7. Save or link the receipt path in the operator handoff.

## Protected surfaces

Any Buildroom component must block rather than proceed if allowed paths intersect, contain, or are contained by protected surfaces. Protected surfaces include at minimum:

- `~/.hermes/config.yaml`
- `~/.hermes/.env`
- `~/.hermes/auth.json`
- gateway/platform credential or route configuration
- Cloudflare tunnel config
- production trading/broker state
- `/Users/caseymoore/Projects/hermes-trading-cockpit`
- cron job definitions

## Before discussing cron

Do not discuss enabling cron until at least one real Research/Subc intake pilot has produced saved receipts with:

- validated room artifacts;
- dry-run proposal output only;
- unchanged Kanban state;
- unchanged cron state;
- no protected-surface hits;
- explicit human/operator approval of the next phase.

A future Phase 2 cron, if approved separately, should be script-only/no-agent, honor `buildroom.lock`, write receipts, stay silent when no candidate exists, and never create Kanban tasks or dispatch workers.
