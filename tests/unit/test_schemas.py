"""Unit tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from opsmind.schemas.discovery import (
    CPUInfo,
    DiscoveryMethod,
    DiscoveryResult,
    HardwareSpec,
    MemoryInfo,
    UnifiedDiscoveryModel,
)
from opsmind.schemas.assessment import (
    AssessmentDimension,
    ComplexityLevel,
    DimensionScore,
    FeasibilityReport,
    RiskLevel,
)
from opsmind.schemas.report import DetailLevel, ReportFormat, ReportMetadata


class TestDiscoverySchemas:
    """Tests for discovery data models."""

    def test_cpu_info_valid(self):
        cpu = CPUInfo(model="Test CPU", cores=4, threads=8)
        assert cpu.cores == 4
        assert cpu.threads == 8

    def test_cpu_info_threads_not_less_than_cores(self):
        with pytest.raises(ValidationError):
            CPUInfo(model="Bad CPU", cores=8, threads=4)

    def test_memory_info_valid(self):
        mem = MemoryInfo(total_gb=16.0, available_gb=8.0, swap_total_gb=2.0, swap_available_gb=1.0)
        assert mem.total_gb == 16.0
        assert mem.available_gb == 8.0

    def test_memory_info_available_exceeds_total(self):
        with pytest.raises(ValidationError):
            MemoryInfo(total_gb=8.0, available_gb=16.0, swap_total_gb=2.0, swap_available_gb=1.0)

    def test_hardware_spec_defaults(self):
        hw = HardwareSpec()
        assert hw.hostname == ""
        assert hw.platform == ""
        assert hw.cpu.cores == 0
        assert hw.memory.total_gb == 0.0
        assert hw.disks == []
        assert hw.network_interfaces == []

    def test_unified_model_creation(self):
        model = UnifiedDiscoveryModel()
        assert model.hardware is not None
        assert model.software is not None
        assert model.security is not None
        assert model.metadata is not None

    def test_discovery_result_defaults(self):
        result = DiscoveryResult()
        assert result.total_hosts == 0
        assert result.successful_hosts == 0
        assert result.failed_hosts == 0
        assert result.hosts == {}
        assert result.errors == {}

    def test_discovery_method_enum(self):
        assert DiscoveryMethod.ANSIBLE.value == "ansible"
        assert DiscoveryMethod.NATIVE.value == "native"
        assert DiscoveryMethod.MOCK.value == "mock"
        assert DiscoveryMethod.AUTO.value == "auto"


class TestAssessmentSchemas:
    """Tests for assessment data models."""

    def test_dimension_score_validation(self):
        ds = DimensionScore(
            dimension=AssessmentDimension.HARDWARE_COMPATIBILITY,
            score=75.0,
            weight=0.3,
        )
        assert ds.score == 75.0
        assert ds.weight == 0.3

    def test_dimension_score_out_of_range(self):
        with pytest.raises(ValidationError):
            DimensionScore(
                dimension=AssessmentDimension.HARDWARE_COMPATIBILITY,
                score=150.0,
                weight=0.3,
            )

    def test_feasibility_report_defaults(self):
        report = FeasibilityReport()
        assert report.overall_score == 0.0
        assert report.complexity == ComplexityLevel.MODERATE
        assert report.risk_level == RiskLevel.MEDIUM
        assert report.dimension_scores == []

    def test_complexity_level_enum(self):
        assert ComplexityLevel.SIMPLE.value == "simple"
        assert ComplexityLevel.MODERATE.value == "moderate"
        assert ComplexityLevel.COMPLEX.value == "complex"
        assert ComplexityLevel.BLOCKER.value == "blocker"


class TestReportSchemas:
    """Tests for report data models."""

    def test_report_metadata_defaults(self):
        meta = ReportMetadata()
        assert meta.title == "OpsMind Assessment Report"
        assert meta.tool_version == "0.1.0"
        assert meta.total_hosts == 0

    def test_report_format_enum(self):
        assert ReportFormat.MARKDOWN.value == "markdown"
        assert ReportFormat.JSON.value == "json"
        assert ReportFormat.HTML.value == "html"

    def test_detail_level_enum(self):
        assert DetailLevel.EXECUTIVE.value == "executive"
        assert DetailLevel.SUMMARY.value == "summary"
        assert DetailLevel.DETAILED.value == "detailed"
        assert DetailLevel.RAW.value == "raw"
