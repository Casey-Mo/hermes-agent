# Buildroom dry-run autonomous proposal receipt — t_d9af34e4

> **Historical receipt note:** This receipt records the original prototype dry run. Its "known gaps" and `coder`/worktree notes were accurate at the time. The current branch has since landed the proposal engine on the primary Buildroom stack, maps proposal assignees to real profiles, uses deterministic idempotency, and honors `buildroom.lock`. See `docs/buildroom/manual-dry-run-deployment.md` for the current deployment runbook.

Generated: 2026-05-11T05:42:54Z
Workspace: `/Users/caseymoore/.hermes/hermes-agent`
Proposal engine source used: `/Users/caseymoore/.hermes/hermes-agent/.worktrees/t_2417ce16/hermes_cli/buildroom/proposal.py`
Candidate fixture used: `/Users/caseymoore/.hermes/hermes-agent/.worktrees/t_2417ce16/tests/fixtures/buildroom/demo-chain`
Runtime receipt root: `/Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_d9af34e4/proposal-20260511T054252Z`

## Candidate

Used the sanitized Buildroom demo chain as the low-risk candidate:

- `chain_id`: `demo-buildroom-0`
- `risk_band`: `1`
- `risk_level`: `additive`
- Allowed paths from product-plan:
  - `hermes_cli/buildroom/`
  - `tests/fixtures/buildroom/`
  - `tests/test_buildroom_validator.py`
  - `docs/buildroom/`
- Protected surfaces listed by the fixture:
  - `~/.hermes/.env`
  - `~/.hermes/auth.json`
  - `~/.hermes/config.yaml`
  - gateway/platform config
  - Cloudflare tunnel config
  - production trading/broker state

This is sanitized fixture data only. No HTC repository, secrets/auth files, Hermes config, gateway/platform config, Cloudflare, broker/trading state, or cron config was edited.

## Commands and results

### 1. Pre-state snapshot

Command:

```bash
python3 -c '... query /Users/caseymoore/.hermes/kanban/boards/hermes/kanban.db and /Users/caseymoore/.hermes/cron/jobs.json ...' > tmp/buildroom-runtime/t_d9af34e4/proposal-20260511T054252Z/pre-state.json
```

Result:

```json
{
  "kanban_db": "/Users/caseymoore/.hermes/kanban/boards/hermes/kanban.db",
  "tasks_total": 19,
  "br_proposal_idempotency_tasks": 0,
  "matching_tasks": [],
  "cron_jobs_count": 2,
  "cron_jobs_sha256": "7a116b9d988e928a28ba10606b772448f3cb08a492a2cb4af6c8d9d0382fe231",
  "timestamp": "2026-05-11T05:42:52Z"
}
```

### 2. Proposal engine targeted tests

Command:

```bash
cd /Users/caseymoore/.hermes/hermes-agent/.worktrees/t_2417ce16
PYTHONPATH="$PWD" /Users/caseymoore/.hermes/hermes-agent/venv/bin/python \
  -m pytest tests/test_buildroom_proposal.py -q
```

Result:

```text
26 passed in 1.58s
```

### 3. Fixture validation

Command:

```bash
PYTHONPATH="$PWD" /Users/caseymoore/.hermes/hermes-agent/venv/bin/python \
  -m hermes_cli.buildroom.validator tests/fixtures/buildroom/demo-chain --json \
  > /Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_d9af34e4/proposal-20260511T054252Z/validator.json
```

Result:

```json
{
  "valid": true,
  "artifact_count": 12
}
```

### 4. Dry-run proposal engine

Command:

```bash
PYTHONPATH="$PWD" /Users/caseymoore/.hermes/hermes-agent/venv/bin/python \
  -m hermes_cli.buildroom.proposal tests/fixtures/buildroom/demo-chain --format json \
  > /Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_d9af34e4/proposal-20260511T054252Z/proposal.json

PYTHONPATH="$PWD" /Users/caseymoore/.hermes/hermes-agent/venv/bin/python \
  -m hermes_cli.buildroom.proposal tests/fixtures/buildroom/demo-chain --format markdown \
  > /Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_d9af34e4/proposal-20260511T054252Z/proposal.md
```

Result summary:

```json
{
  "status": "dry-run",
  "approved": true,
  "execute": false,
  "chain_id": "demo-buildroom-0",
  "risk_band": 1,
  "risk_level": "additive",
  "gates_passed": 4,
  "task_graph_count": 4
}
```

Saved artifacts:

- `/Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_d9af34e4/proposal-20260511T054252Z/proposal.json`
- `/Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_d9af34e4/proposal-20260511T054252Z/proposal.md`
- `/Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_d9af34e4/proposal-20260511T054252Z/summary.json`

## Proposed Kanban graph

Dry-run only; these were not created on the board.

1. `schemas` — Define artifact envelope and payload models
2. `fixture` — Create full sanitized demo chain; parent: `schemas`
3. `validator` — Check order, parent consistency, schemas, and terminal states; parent: `fixture`
4. `summary` — Build sanitized operator summary; parent: `validator`

Every proposed node had `assignee_profile: "coder"` in this prototype. That is acceptable for a static proposal receipt, but it is a Phase-2/Phase-3 footgun before any supervised auto-create because profile routing should be explicit and risk-aware.

## Dry-run side-effect verification

Post-state snapshot result:

```json
{
  "kanban_db": "/Users/caseymoore/.hermes/kanban/boards/hermes/kanban.db",
  "tasks_total": 19,
  "br_proposal_idempotency_tasks": 0,
  "matching_tasks": [],
  "cron_jobs_count": 2,
  "cron_jobs_sha256": "7a116b9d988e928a28ba10606b772448f3cb08a492a2cb4af6c8d9d0382fe231",
  "timestamp": "2026-05-11T05:42:54Z"
}
```

Confirmed:

- Kanban task count did not change: `19 -> 19`.
- No `br-proposal-*` idempotency-key tasks existed before or after: `0 -> 0`.
- No Buildroom-to-Kanban matching task rows existed before or after: `[] -> []`.
- Cron job count did not change: `2 -> 2`.
- Cron jobs file hash did not change: `7a116b9d988e928a28ba10606b772448f3cb08a492a2cb4af6c8d9d0382fe231` before and after.

## Recommendation

Do not approve supervised auto-create yet.

The dry run itself behaved correctly: it produced a human-reviewable graph, set `execute=false`, and did not create tasks or cron jobs. But the currently reviewed proposal/validator branch still has safety blockers from parent task `t_281e2111`:

1. Protected-surface checks need parent/child path containment, tilde expansion, and normalization. Exact set-intersection is not enough.
2. The documented `~/.hermes/buildroom.lock` global off-switch must be implemented and verified before any adapter can run outside one-off manual dry runs.
3. Proposed assignees and idempotency keys need hardening before any auto-create mode: no hardcoded universal `coder`; deterministic idempotency should not include current time if it is used to dedupe.

After those fixes pass independent review, Casey could consider a later supervised auto-create pilot with this narrow scope only:

- docs-only changes,
- tests-only additions or fixture updates,
- QA-tooling/buildroom/operator-visibility improvements,
- non-running proposal/notification cards only,
- no auto-dispatch,
- no cron creation/enabling without separate explicit approval,
- no protected surfaces, secrets/auth files, gateway/platform config, Cloudflare, broker/trading state, or HTC product repository paths.

Initial approval wording should be explicit, for example: "Approve supervised Buildroom auto-create for low-risk docs/tests/QA-tooling proposal cards only, no worker dispatch, no cron changes, honor `~/.hermes/buildroom.lock`, and block on protected-surface or risk-band violations."

## Rollback / off-switch notes

Generated files can be removed with:

```bash
rm -rf /Users/caseymoore/.hermes/hermes-agent/tmp/buildroom-runtime/t_d9af34e4/proposal-20260511T054252Z
rm -f /Users/caseymoore/.hermes/hermes-agent/docs/buildroom/proposal-receipt-t_d9af34e4.md
```

No production off-switch was needed for this run because no autonomous dispatch, cron job, config, gateway route, Cloudflare route, broker/trading setting, or production Kanban write was created. Before any future runtime/supervised mode, implement and test the documented `~/.hermes/buildroom.lock` stop file.

## Known gaps

- The proposal engine used here lives in `.worktrees/t_2417ce16`, not on `main` in the primary workspace at the time of this receipt.
- This was a sanitized fixture pilot, not a live Research/Subc intake.
- The dry-run graph is a proposal artifact only; it is not yet safe to convert into live Kanban tasks until the parent safety blockers are fixed and reviewed.
