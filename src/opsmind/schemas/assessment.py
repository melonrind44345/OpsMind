"""Pydantic models for assessment data."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AssessmentDimension(StrEnum):
    """Assessment dimension categories."""

    HARDWARE_COMPATIBILITY = "hardware_compatibility"
    SOFTWARE_SUPPORT = "software_support"
    CONFIG_COMPLEXITY = "config_complexity"
    SECURITY_BASELINE = "security_baseline"


class ComplexityLevel(StrEnum):
    """Complexity levels for modernization."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    BLOCKER = "blocker"


class RiskLevel(StrEnum):
    """Risk level assessment."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DimensionScore(BaseModel):
    """Score for a single assessment dimension."""

    dimension: AssessmentDimension
    score: float = Field(default=0.0, ge=0.0, le=100.0, description="Score 0-100")
    weight: float = Field(default=0.0, ge=0.0, le=1.0, description="Weight in overall calculation")
    findings: list[str] = Field(default_factory=list, description="Specific findings")
    issues: list[str] = Field(default_factory=list, description="Identified issues")
    recommendations: list[str] = Field(default_factory=list, description="Recommendations")


class IssueDetail(BaseModel):
    """Detailed issue description."""

    category: str = Field(description="Issue category")
    severity: RiskLevel = Field(description="Issue severity")
    title: str = Field(description="Issue title")
    description: str = Field(description="Detailed description")
    impact: str = Field(description="Impact description")
    recommendation: str = Field(description="Recommended action")
    affected_components: list[str] = Field(default_factory=list, description="Affected components")


class FeasibilityReport(BaseModel):
    """Containerization feasibility assessment report."""

    overall_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Overall feasibility score")
    dimension_scores: list[DimensionScore] = Field(default_factory=list, description="Per-dimension scores")
    complexity: ComplexityLevel = Field(default=ComplexityLevel.MODERATE, description="Overall complexity")
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM, description="Overall risk level")
    issues: list[IssueDetail] = Field(default_factory=list, description="All identified issues")
    recommendations: list[str] = Field(default_factory=list, description="Top recommendations")
    summary: str = Field(default="", description="Executive summary")
    assess_algorithm: str = Field(default="opsmind-weighted-v1", description="Assessment algorithm used")


class ComplexityAssessment(BaseModel):
    """Detailed complexity assessment."""

    level: ComplexityLevel = Field(default=ComplexityLevel.SIMPLE, description="Complexity level")
    score: float = Field(default=0.0, ge=0.0, le=100.0, description="Complexity score")
    factors: dict[str, float] = Field(default_factory=dict, description="Contributing factors and their scores")
    breakdown: str = Field(default="", description="Detailed breakdown")
    estimated_effort_days: int | None = Field(default=None, description="Estimated effort in days")
    skill_requirements: list[str] = Field(default_factory=list, description="Required skills")


class ResourceSizing(BaseModel):
    """Recommended resource sizing for containerization."""

    cpu_cores: float = Field(default=1.0, ge=0.1, description="Recommended CPU cores")
    memory_gb: float = Field(default=1.0, ge=0.1, description="Recommended memory in GB")
    storage_gb: float = Field(default=10.0, ge=0.1, description="Recommended storage in GB")
    replicas: int = Field(default=1, ge=1, description="Recommended replica count")
    rationale: str = Field(default="", description="Sizing rationale")
    optimizations: list[str] = Field(default_factory=list, description="Optimization suggestions")


class MigrationStrategy(BaseModel):
    """Migration strategy recommendations."""

    strategy_type: str = Field(default="", description="Strategy type (rehost, refactor, rebuild, etc.)")
    phases: list[dict[str, Any]] = Field(default_factory=list, description="Migration phases")
    estimated_duration_days: int | None = Field(default=None, description="Total estimated duration")
    risks: list[str] = Field(default_factory=list, description="Identified risks")
    rollback_strategy: str = Field(default="", description="Rollback plan description")


class AssessmentResult(BaseModel):
    """Complete assessment result."""

    host: str = Field(description="Assessed host")
    feasibility: FeasibilityReport = Field(default_factory=FeasibilityReport, description="Feasibility report")
    complexity: ComplexityAssessment = Field(default_factory=ComplexityAssessment, description="Complexity assessment")
    resource_sizing: ResourceSizing = Field(default_factory=ResourceSizing, description="Resource sizing")
    migration_strategy: MigrationStrategy = Field(default_factory=MigrationStrategy, description="Migration strategy")
    assessed_at: datetime = Field(default_factory=datetime.now, description="When assessment was performed")
    data_source: str = Field(default="ansible", description="Source of data for assessment")
