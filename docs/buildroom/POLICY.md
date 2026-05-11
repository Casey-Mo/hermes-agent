# Hermes Self-Development Safety & Governance Policy

This policy governs the autonomous and semi-autonomous development of the Hermes Agent codebase (`/Users/caseymoore/.hermes/hermes-agent`). It defines the boundaries between research, planning, execution, and oversight.

## 1. Risk Bands

All Buildroom jobs must be categorized by risk before a `product-plan` is approved.

| Band | Name | Definition | Allowed Actions | Handoff Requirement |
|---|---|---|---|---|
| **Band 0** | Documentation | Refactorings, comments, docs, type hints. No logic changes. | Write to `.md`, `.py` (non-functional). | Auto-QA pass + Human notification. |
| **Band 1** | Additive | New plugins, new tools, new optional-skills. Isolated files. | Create new files in `plugins/`, `tools/`. | Independent QA + Human approval (Main). |
| **Band 2** | Modified Logic | Functional changes to existing logic or toolsets. | Patch existing `hermes_cli/`, `tools/`. | Mandatory Human `Main-Review`. |
| **Band 3** | Core Loop | Modifications to `run_agent.py`, `agent/`, `gateway/`. | Any change to the core loop or transport. | **Forbidden** for autonomous build. Manual only. |

### 1.1 Protected Surfaces (Forbidden for Auto-Build)
- `~/.hermes/config.yaml` and `~/.hermes/.env`.
- `gateway/platforms/` (existing credentials/routes).
- `hermes_state.py` (database schema).
- `/Users/caseymoore/Projects/hermes-trading-cockpit` (HTC Product).

## 2. Signal Thresholds & Intake

Signals from `Research` via `subc-handoff.json` must meet these criteria to become a `research-input`:

- **Confidence Score**: Minimum `0.8` for Band 1/2; No limit for Band 0.
- **Evidence Count**: Minimum 3 distinct sources (mentions, logs, or vault entries).
- **Cooldown**: A specific command, tool, or plugin cannot be "re-designed" more than once every 14 days (Sprint Lock).
- **Sprint Lock**: Max 3 active Buildroom jobs at any time. New signals are queued until a room reaches `retention-review`.

## 3. The Contract Chain & Artifacts

Every job must produce these artifacts in order. Each is a hard gate.

1. **research-input**: Raw evidence, confidence, and source links.
2. **idea-contract**: Synthesis of "Why this makes Hermes better."
3. **intent-review (Gate 1)**: Main profile approves the intent.
4. **main-review (Gate 2)**: Strategic alignment check; assigns the **Risk Band**.
5. **product-plan (Gate 3)**: Analyst defines `allowed_paths`, `protected_surfaces`, and `verification_commands`.
6. **build-plan**: Coder maps tasks to specific file edits.
7. **verification**: Raw build output and test results.
8. **qa-verification (Gate 4)**: Independent profile (QA) reproduces verification.
9. **verification-delta**: List of remaining gaps or "none".
10. **trust-report (Gate 5)**: Trust certifies safety state.
11. **retention-review**: Retention evaluates cost/value.
12. **operator-summary**: Redacted human-facing receipt.

## 4. Kanban Task Creation Rules

Buildroom jobs may interact with the Kanban board only under these phase-gated conditions:

- **Phase 1 / current mode:** no automatic Kanban task creation and no automatic dispatch. Buildroom outputs stop at artifacts, validation, and an operator summary.
- **Future success feedback:** after explicit Casey approval to enter a later phase, a completed buildroom job may create a non-running notification/proposal card only; it must not create implementation cards or mark anything `ready`.
- **Manual intervention:** any buildroom component may block and ask Casey when it touches a protected surface or requires credentials it does not have.
- **Auto-dispatch:** forbidden in v1. No buildroom path may spawn workers, dispatch Kanban, or mutate board state beyond explicit human-triggered CLI commands.

## 5. Phase Gates: Evolution toward Autonomy

Hermes development moves through these phases. We are currently in **Phase 1**.

| Phase | Mode | Execution | Approval |
|---|---|---|---|
| **Phase 1** | Proposal-only | Manual trigger of `handoff.py`. | Human writes all artifacts 3–12. |
| **Phase 2** | Dry-run | Cron triggers `handoff.py` & `validator`. | Human reviews JSON artifacts in the vault. |
| **Phase 3** | Supervised | Agents generate all artifacts. | **Human must unblock** at `intent-review` and `trust-report`. |
| **Phase 4** | Limited Auto | Band 0/1 tasks can auto-complete. | Human reviews `operator-summary` post-facto. |

## 6. Feedback Loop

After `retention-review`, the outcome (success/fail/usage/cost) is written back to the **Research Vault** under `knowledge/buildroom-outcomes.json`. Research uses this to calibrate future Signal Thresholds (e.g., if many Band 1 tools are discarded, increase the intake threshold).

## 7. Safety Invariants (The "Off Switch")

1. **Path Enforcement**: The `validator` tool MUST verify that no file changed outside of `product-plan.allowed_paths`. Any violation results in an immediate `trust_state=blocked`.
2. **Secret Scrubbing**: `operator-summary` must redact any string matching `sk-*`, `xai-*`, or `Authorization: Bearer`.
3. **Global Lock**: Creating a file at `~/.hermes/buildroom.lock` stops all active buildroom adapters immediately.
