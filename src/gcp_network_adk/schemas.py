from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"]
InsightState = Literal["ACTIVE", "ACCEPTED", "DISMISSED", "UNKNOWN"]
RiskLevel = Literal["low", "medium", "high"]


class ScanRequest(BaseModel):
    project_ids: list[str] = Field(default_factory=list)
    location: str = "global"
    insight_types: list[str] = Field(default_factory=list)
    max_results_per_type: int = 100
    include_accepted: bool = False
    include_dismissed: bool = False

    @field_validator("project_ids")
    @classmethod
    def validate_project_ids(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("At least one project_id is required")
        return cleaned

    @field_validator("max_results_per_type")
    @classmethod
    def validate_max_results(cls, value: int) -> int:
        if value < 1 or value > 1000:
            raise ValueError("max_results_per_type must be between 1 and 1000")
        return value


class NormalisedInsight(BaseModel):
    project_id: str
    location: str
    insight_id: str
    insight_name: str
    insight_type: str
    subtype: str | None = None
    category: str | None = None
    severity: Severity = "UNKNOWN"
    state: InsightState = "UNKNOWN"
    description: str
    target_resources: list[str] = Field(default_factory=list)
    content: dict[str, Any] = Field(default_factory=dict)
    last_refresh_time: str | None = None
    raw_etag: str | None = None
    recommendation_hint: str | None = None


class ScanResult(BaseModel):
    scan_scope: dict[str, Any]
    insights: list[NormalisedInsight] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)


class RecommendationItem(BaseModel):
    insight_id: str
    project_id: str
    problem_summary: str
    likely_root_cause: str
    recommended_action: str
    why_this_fix: str
    risk_level: RiskLevel
    confidence: float
    validation_steps: list[str] = Field(default_factory=list)
    rollback_plan: list[str] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    terraform_notes: list[str] = Field(default_factory=list)
    needs_human_review: bool = True


class RecommendationBatch(BaseModel):
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    grouped_summary: dict[str, Any] = Field(default_factory=dict)