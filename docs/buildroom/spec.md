# Hermes Buildroom Contract Chain & Safety Acceptance Plan

Goal: define a Hermes-wide, dry-run Buildroom contract chain that lets existing profiles hand structured artifacts to one another before any adapter executes work.

Buildroom v1 is manual/proposal-first only. It validates JSON handoff artifacts and summarizes readiness; it must not create Kanban tasks, mutate runtime config, touch secrets, or edit HTC product repositories.

## Full pipeline (Research → Subc/Dreamer → Main → Coder → QA → Trust → Retention)

```
Research                gathers raw evidence into the research vault
    │
    ▼ queue/subc-handoff.json
Subc/Dreamer            notices patterns, walks signals, builds signal state
    │
    ▼  buildroom/handoff.py  (dry-run adapter, no approval)
Main                    approves or rejects intent (intent-review + main-review)
    │
    ▼  (if approved)
Analyst                 produces bounded product-plan with guardrails
    │
    ▼
Coder                   builds to spec, records verification
    │
    ▼
QA                      independently verifies (qa-verification + verification-delta)
    │
    ▼
Trust                   reports safety/quality state
    │
    ▼
Retention               reviews value/cost outcome
    │
    ▼
Analyst                 prepares operator summary with redacted values
```

### Step-by-step

1. **Research → queue/subc-handoff.json** — Research profile runs its collector crons (X, bookmarks, Open Brain) and writes signals to `queue/subc-handoff.json` in the research vault. This is a structured JSON with topic, signal text, confidence, and suggested walk mode.

2. **Subc/Dreamer reads subc-handoff.json** — The Subc/Dreamer profile's cron or manual walk picks up the handoff, walks signals through its signal-state system, and updates its signal log. It produces no Buildroom artifacts directly; it maintains its own signal-state summary.

3. **Buildroom handoff adapter (`hermes_cli/buildroom/handoff.py`)** — This is a manual or cron-triggered dry-run adapter. It reads `subc-handoff.json` from the research vault and creates a dry-run Buildroom room directory containing exactly two artifacts:
   - `research-input.json` (profile: "research") — wraps the subc handoff signals as evidence.
   - `idea-contract.json` (profile: "subc") — synthesizes a concrete proposal from the signals.

   The adapter does **not** create intent-review, main-review, or any downstream artifact. It does **not** create Kanban tasks, cron jobs, or mutate Hermes config. It is safe for no-agent cron dry-run: pure JSON write, zero side effects.

4. **Main review** — A human or Main profile reviews the idea-contract and produces `intent-review` and `main-review` artifacts to approve, reject, or narrow scope. This is the first approval gate.

5. **Analyst → Product plan** — An analyst profile produces a bounded product-plan with allowed paths, non-goals, verification commands, risks, and protected surfaces.

6. **Coder → Build + Verify** — Coder builds to the spec and records verification evidence.

7. **QA → Independent verification** — QA independently verifies artifacts and records delta state.

8. **Trust → Trust report** — Trust reports safety/quality state; requires independent QA to pass.

9. **Retention → Review** — Retention reviews value/cost outcome.

10. **Operator summary** — Analyst prepares a human-facing summary with redacted secret-like values.

## Contract artifacts and order

1. `research-input` — research profile records raw signals and source evidence.
2. `idea-contract` — subc profile converts signals into a concrete proposal.
3. `intent-review` — main profile approves, rejects, or narrows scope.
4. `main-review` — main profile checks strategic/business alignment.
5. `product-plan` — analyst profile defines UX, acceptance criteria, allowed paths, non-goals, verification commands, risks, and protected surfaces.
6. `build-plan` — coder profile defines files, tasks, tests, and rollback plan.
7. `verification` — coder profile records build/test evidence.
8. `qa-verification` — QA profile independently verifies artifacts.
9. `verification-delta` — QA profile records required follow-up or `none`.
10. `trust-report` — trust profile records safety/quality state.
11. `retention-review` — retention profile records value/cost outcome.
12. `operator-summary` — analyst profile prepares the human-facing summary.

## Safety gates

- Independent QA is required before `trust_state=trusted`.
- `verification-delta.delta_state=none` must have no required actions.
- Demo/runtime rooms must not end with `retention_state=discard`.
- Operator summaries expose counts/states/next actions rather than raw evidence, and redact secret-like values before display.
- Product plans must be bounded with allowed paths, non-goals, verification commands, risks, and protected surfaces before any coder receives a build plan.
- The handoff adapter (`handoff.py`) is explicitly limited to creating only `research-input` and `idea-contract`. It must never create approval artifacts, Kanban tasks, cron jobs, or mutate Hermes config. This is enforced by the test suite.
- v1 has no autonomous execution, no cron wiring, and no production writes.

## Off switch and rollback

The validator and handoff adapter are read-only and have no daemon, scheduler, or persistent runtime. Rollback is removing `hermes_cli/buildroom/`, `tests/test_buildroom_validator.py`, `tests/test_buildroom_adapter.py`, `tests/fixtures/buildroom/`, and these docs.

Future adapter wiring should add explicit dry-run flags and respect any global Buildroom lock file before runtime integration is enabled.

## Running the handoff adapter

```bash
# Dry-run from a fixture
python -m hermes_cli.buildroom.handoff \
    --handoff tests/fixtures/buildroom/fixture-handoff/subc-handoff.json \
    --output /tmp/buildroom-dry-run

# The adapter prints the room path to stdout
```

## Running validation

```bash
python -m pytest tests/ -k buildroom -q
```
