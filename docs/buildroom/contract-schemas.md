# Buildroom Contract Schemas

The first Buildroom scaffold lives under `hermes_cli/buildroom/` and defines one typed Pydantic envelope per required artifact. All artifacts share these envelope fields:

- `contract_id`
- `parent_id`
- `chain_id`
- `artifact_type`
- `version`
- `timestamp`
- `profile`
- `payload`

The required artifact order is exported as `REQUIRED_ARTIFACT_ORDER` from `hermes_cli.buildroom.schemas`.

## Required states

- `verification-delta.payload.delta_state`: `none`, `open`, `addressed`, or `rejected`
- `trust-report.payload.trust_state`: `trusted`, `conditional`, or `blocked`
- `retention-review.payload.retention_state`: `retain`, `archive`, or `discard`

The validator adds cross-artifact checks beyond Pydantic schema validation:

- every required artifact type is present exactly in the expected order;
- filename prefixes match the chain order (`01-`, `02-`, ...);
- all artifacts share a `chain_id`;
- `parent_id` matches the previous artifact's `contract_id`;
- contract IDs are unique;
- trusted reports require independent QA;
- a no-delta state cannot carry required actions;
- demo/runtime rooms cannot end in discard state.

`product-plan.payload` is intentionally bounded. It must declare `allowed_paths`,
`non_goals`, `verification_commands`, `risks`, and `protected_surfaces` in addition
to the user story and acceptance criteria. This keeps downstream coding adapters
from receiving an unbounded plan.

Operator summaries omit raw evidence text and redact known secret-like values
(`sk-*`, `xai-*`, Google API key shapes, GitHub tokens, and bearer tokens) before
returning dashboard/handoff-safe summaries.

## Demo fixture

`tests/fixtures/buildroom/demo-chain/` contains a sanitized 12-artifact chain for `demo-buildroom-0`. It intentionally references only docs, Kanban metadata, and local command names; it does not contain credentials, runtime config, or production data.

## Running validation

```bash
python -m pytest tests/ -k buildroom -q
python -m hermes_cli.buildroom.validator tests/fixtures/buildroom/demo-chain
python -m hermes_cli.buildroom.validator tests/fixtures/buildroom/demo-chain --json
```
