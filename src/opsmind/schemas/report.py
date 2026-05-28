"""Pydantic models for report data."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from opsmind.schemas.assessment import AssessmentResult


class ReportFormat(StrEnum):
    """Supported report output formats."""

    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"


class DetailLevel(StrEnum):
    """Report detail granularity."""

    EXECUTIVE = "executive"
    SUMMARY = "summary"
    DETAILED = "detailed"
    RAW = "raw"


class ReportSection(BaseModel):
    """A section within a report."""

    title: str = Field(description="Section title")
    content: str = Field(description="Section content (markdown)")
    subsections: list["ReportSection"] = Field(default_factory=list, description="Sub-sections")
    data_refs: list[str] = Field(default_factory=list, description="References to underlying data")


class ReportMetadata(BaseModel):
    """Metadata about the report itself."""

    title: str = Field(default="OpsMind Assessment Report", description="Report title")
    generated_at: datetime = Field(default_factory=datetime.now, description="When report was generated")
    tool_version: str = Field(default="0.1.0", description="OpsMind version")
    data_source: str = Field(default="", description="Source of the data")
    confidence: str = Field(default="", description="Overall confidence level")
    total_hosts: int = Field(default=0, description="Number of hosts in report")
    generation_duration_ms: float = Field(default=0.0, description="Report generation time")


class ReportData(BaseModel):
    """Complete report data model."""

    metadata: ReportMetadata = Field(default_factory=ReportMetadata, description="Report metadata")
    executive_summary: str = Field(default="", description="Executive summary")
    discovery_summary: dict[str, Any] = Field(default_factory=dict, description="Discovery results summary")
    assessment_summary: dict[str, Any] = Field(default_factory=dict, description="Assessment results summary")
    host_reports: dict[str, AssessmentResult] = Field(default_factory=dict, description="Per-host assessments")
    global_recommendations: list[str] = Field(default_factory=list, description="Global recommendations")
    generated_files: list[str] = Field(default_factory=list, description="Generated output files")
    sections: list[ReportSection] = Field(default_factory=list, description="Report sections")


class ReportComparison(BaseModel):
    """Comparison between two assessment reports."""

    before_report: str = Field(description="Path to baseline report")
    after_report: str = Field(description="Path to comparison report")
    score_delta: float = Field(default=0.0, description="Change in overall score")
    hosts_added: list[str] = Field(default_factory=list, description="Hosts in after but not before")
    hosts_removed: list[str] = Field(default_factory=list, description="Hosts in before but not after")
    changes: list[dict[str, Any]] = Field(default_factory=list, description="Specific changes detected")
    generated_at: datetime = Field(default_factory=datetime.now, description="Comparison timestamp")
