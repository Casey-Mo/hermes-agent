# Hermes Buildroom Contract Chain & Safety Acceptance Plan

Goal: define a Hermes-wide, dry-run Buildroom contract chain that lets existing profiles hand structured artifacts to one another before any adapter executes work.

Buildroom v1 is manual/proposal-first only. It validates JSON handoff artifacts and summarizes readiness; it must not create Kanban tasks, mutate runtime config, touch secrets, or edit HTC product repositories.

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
- v1 has no autonomous execution, no cron wiring, and no production writes.

## Off switch and rollback

The validator is read-only and has no daemon, scheduler, or persistent runtime. Rollback is removing `hermes_cli/buildroom/`, `tests/test_buildroom_validator.py`, `tests/fixtures/buildroom/demo-chain/`, and these docs.

Future adapter wiring should add explicit dry-run flags and respect any global Buildroom lock file before runtime integration is enabled.
