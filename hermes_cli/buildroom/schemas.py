"""Pydantic schemas for Hermes Buildroom contract artifacts.

Buildroom v1 is intentionally dry-run/manual. These schemas describe sanitized
handoff artifacts only; they do not execute plans, create Kanban tasks, or touch
runtime configuration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

NonEmptyString = Annotated[str, Field(min_length=1)]
EvidenceList = Annotated[list[NonEmptyString], Field(min_length=1)]

REQUIRED_ARTIFACT_ORDER: tuple[str, ...] = (
    "research-input",
    "idea-contract",
    "intent-review",
    "main-review",
    "product-plan",
    "build-plan",
    "verification",
    "qa-verification",
    "verification-delta",
    "trust-report",
    "retention-review",
    "operator-summary",
)

DELTA_STATES = frozenset({"none", "open", "addressed", "rejected"})
TRUST_STATES = frozenset({"trusted", "conditional", "blocked"})
RETENTION_STATES = frozenset({"retain", "archive", "discard"})


class StrictPayload(BaseModel):
    """Base class for artifact payloads.

    Extra fields are rejected so sanitized fixtures do not accrete secrets or
    runtime-only data under unreviewed names.
    """

    model_config = ConfigDict(extra="forbid")


class ResearchInputPayload(StrictPayload):
    title: NonEmptyString
    signals: EvidenceList
    evidence: EvidenceList
    constraints: EvidenceList


class IdeaContractPayload(StrictPayload):
    title: NonEmptyString
    problem_statement: NonEmptyString
    proposed_solution: NonEmptyString
    research_refs: EvidenceList
    estimated_impact: NonEmptyString


class IntentReviewPayload(StrictPayload):
    decision: Literal["approved", "rejected", "needs-revision"]
    scope: EvidenceList
    evidence: EvidenceList
    human_approval_required: bool = True


class MainReviewPayload(StrictPayload):
    decision: Literal["aligned", "not-aligned", "needs-revision"]
    risk_band: Literal[0, 1, 2, 3]
    alignment_notes: NonEmptyString
    risks: EvidenceList
    evidence: EvidenceList


class ProductPlanPayload(StrictPayload):
    feature_name: NonEmptyString
    user_story: NonEmptyString
    allowed_paths: EvidenceList
    non_goals: EvidenceList
    verification_commands: EvidenceList
    acceptance_criteria: EvidenceList
    risks: EvidenceList
    protected_surfaces: EvidenceList
    evidence: EvidenceList


class BuildPlanPayload(StrictPayload):
    tasks: list[dict[str, Any]] = Field(min_length=1)
    files_to_touch: EvidenceList
    test_plan: NonEmptyString
    rollback_plan: NonEmptyString
    evidence: EvidenceList


class VerificationPayload(StrictPayload):
    status: Literal["passed", "failed"]
    commands: EvidenceList
    artifacts_produced: EvidenceList
    evidence: EvidenceList
    known_issues: list[str] = Field(default_factory=list)


class QaVerificationPayload(StrictPayload):
    state: Literal["passed", "failed"]
    checked_artifacts: EvidenceList
    evidence: EvidenceList
    reviewer: NonEmptyString


class VerificationDeltaPayload(StrictPayload):
    delta_state: Literal["none", "open", "addressed", "rejected"]
    linked_verification_id: NonEmptyString
    required_actions: list[str] = Field(default_factory=list)
    evidence: EvidenceList


class TrustReportPayload(StrictPayload):
    trust_state: Literal["trusted", "conditional", "blocked"]
    safety_notes: EvidenceList
    evidence: EvidenceList
    independent_qa_confirmed: bool


class RetentionReviewPayload(StrictPayload):
    retention_state: Literal["retain", "archive", "discard"]
    value_assessment: NonEmptyString
    follow_up: EvidenceList
    evidence: EvidenceList


class OperatorSummaryPayload(StrictPayload):
    status: Literal["clean", "needs-review", "blocked"]
    summary: NonEmptyString
    next_actions: EvidenceList
    rollback_note: NonEmptyString


PayloadModel = type[StrictPayload]

ARTIFACT_MODELS: dict[str, PayloadModel] = {
    "research-input": ResearchInputPayload,
    "idea-contract": IdeaContractPayload,
    "intent-review": IntentReviewPayload,
    "main-review": MainReviewPayload,
    "product-plan": ProductPlanPayload,
    "build-plan": BuildPlanPayload,
    "verification": VerificationPayload,
    "qa-verification": QaVerificationPayload,
    "verification-delta": VerificationDeltaPayload,
    "trust-report": TrustReportPayload,
    "retention-review": RetentionReviewPayload,
    "operator-summary": OperatorSummaryPayload,
}

EXPECTED_PROFILES: dict[str, str] = {
    "research-input": "research",
    "idea-contract": "subc",
    "intent-review": "main",
    "main-review": "main",
    "product-plan": "analyst",
    "build-plan": "coder",
    "verification": "coder",
    "qa-verification": "qa",
    "verification-delta": "qa",
    "trust-report": "trust",
    "retention-review": "retention",
    "operator-summary": "analyst",
}


class BaseArtifact(BaseModel):
    """Common envelope for every Buildroom contract artifact."""

    model_config = ConfigDict(extra="forbid")

    contract_id: NonEmptyString
    parent_id: str | None = None
    chain_id: NonEmptyString
    artifact_type: NonEmptyString
    version: NonEmptyString = "1.0.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    profile: NonEmptyString
    payload: dict[str, Any]

    @field_validator("artifact_type")
    @classmethod
    def known_artifact_type(cls, value: str) -> str:
        if value not in ARTIFACT_MODELS:
            raise ValueError(f"unknown buildroom artifact_type: {value}")
        return value


class TypedArtifact(BaseArtifact):
    """Envelope plus a typed payload; subclasses define artifact_type/payload."""

    expected_artifact_type: ClassVar[str]
    expected_profile: ClassVar[str]
    payload: StrictPayload

    @field_validator("artifact_type")
    @classmethod
    def matches_subclass_artifact_type(cls, value: str) -> str:
        if value != cls.expected_artifact_type:
            raise ValueError(
                f"expected artifact_type {cls.expected_artifact_type!r}, got {value!r}"
            )
        return value

    @field_validator("profile")
    @classmethod
    def matches_expected_profile(cls, value: str) -> str:
        if value != cls.expected_profile:
            raise ValueError(
                f"expected profile {cls.expected_profile!r}, got {value!r}"
            )
        return value


class ResearchInputArtifact(TypedArtifact):
    expected_artifact_type: ClassVar[str] = "research-input"
    expected_profile: ClassVar[str] = "research"
    payload: ResearchInputPayload


class IdeaContractArtifact(TypedArtifact):
    expected_artifact_type: ClassVar[str] = "idea-contract"
    expected_profile: ClassVar[str] = "subc"
    payload: IdeaContractPayload


class IntentReviewArtifact(TypedArtifact):
    expected_artifact_type: ClassVar[str] = "intent-review"
    expected_profile: ClassVar[str] = "main"
    payload: IntentReviewPayload


class MainReviewArtifact(TypedArtifact):
    expected_artifact_type: ClassVar[str] = "main-review"
    expected_profile: ClassVar[str] = "main"
    payload: MainReviewPayload


class ProductPlanArtifact(TypedArtifact):
    expected_artifact_type: ClassVar[str] = "product-plan"
    expected_profile: ClassVar[str] = "analyst"
    payload: ProductPlanPayload


class BuildPlanArtifact(TypedArtifact):
    expected_artifact_type: ClassVar[str] = "build-plan"
    expected_profile: ClassVar[str] = "coder"
    payload: BuildPlanPayload


class VerificationArtifact(TypedArtifact):
    expected_artifact_type: ClassVar[str] = "verification"
    expected_profile: ClassVar[str] = "coder"
    payload: VerificationPayload


class QaVerificationArtifact(TypedArtifact):
    expected_artifact_type: ClassVar[str] = "qa-verification"
    expected_profile: ClassVar[str] = "qa"
    payload: QaVerificationPayload


class VerificationDeltaArtifact(TypedArtifact):
    expected_artifact_type: ClassVar[str] = "verification-delta"
    expected_profile: ClassVar[str] = "qa"
    payload: VerificationDeltaPayload


class TrustReportArtifact(TypedArtifact):
    expected_artifact_type: ClassVar[str] = "trust-report"
    expected_profile: ClassVar[str] = "trust"
    payload: TrustReportPayload


class RetentionReviewArtifact(TypedArtifact):
    expected_artifact_type: ClassVar[str] = "retention-review"
    expected_profile: ClassVar[str] = "retention"
    payload: RetentionReviewPayload


class OperatorSummaryArtifact(TypedArtifact):
    expected_artifact_type: ClassVar[str] = "operator-summary"
    expected_profile: ClassVar[str] = "analyst"
    payload: OperatorSummaryPayload


ARTIFACT_ENVELOPE_MODELS: dict[str, type[TypedArtifact]] = {
    "research-input": ResearchInputArtifact,
    "idea-contract": IdeaContractArtifact,
    "intent-review": IntentReviewArtifact,
    "main-review": MainReviewArtifact,
    "product-plan": ProductPlanArtifact,
    "build-plan": BuildPlanArtifact,
    "verification": VerificationArtifact,
    "qa-verification": QaVerificationArtifact,
    "verification-delta": VerificationDeltaArtifact,
    "trust-report": TrustReportArtifact,
    "retention-review": RetentionReviewArtifact,
    "operator-summary": OperatorSummaryArtifact,
}


def artifact_json_schemas() -> dict[str, dict[str, Any]]:
    """Return JSON-schema dictionaries for all Buildroom artifact envelopes."""

    return {
        artifact_type: model.model_json_schema()
        for artifact_type, model in ARTIFACT_ENVELOPE_MODELS.items()
    }
