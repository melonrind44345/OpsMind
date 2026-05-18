"""Unit tests for assessment evaluators."""

import json
from pathlib import Path

import pytest

from opsmind.assessment.evaluators.feasibility import ContainerizationFeasibilityEvaluator
from opsmind.assessment.evaluators.complexity import ComplexityEvaluator
from opsmind.assessment.evaluators.security import SecurityEvaluator
from opsmind.discovery.adapters.ansible_adapter import AnsibleFactAdapter
from opsmind.discovery.engines.mock_engine import MockDiscoveryEngine
from opsmind.schemas.assessment import ComplexityLevel, RiskLevel


@pytest.fixture
def legacy_candidate():
    """Get legacy system data for testing."""
    engine = MockDiscoveryEngine(profile="legacy-centos")
    result = engine.discover_host("legacy-centos")
    return list(result.hosts.values())[0]


@pytest.fixture
def modern_candidate():
    """Get modern system data for testing."""
    engine = MockDiscoveryEngine(profile="modern-ubuntu")
    result = engine.discover_host("modern-ubuntu")
    return list(result.hosts.values())[0]


class TestFeasibilityEvaluator:
    """Tests for containerization feasibility evaluation."""

    def setup_method(self):
        self.evaluator = ContainerizationFeasibilityEvaluator()

    def test_legacy_system_assessment(self, legacy_candidate):
        report = self.evaluator.evaluate(legacy_candidate)

        assert report.overall_score >= 0
        assert report.overall_score <= 100

        # Legacy CentOS 6 should have moderate-to-low score
        assert report.complexity in (ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX, ComplexityLevel.BLOCKER)

        assert len(report.dimension_scores) == 4
        assert len(report.recommendations) > 0
        assert report.summary != ""

    def test_modern_system_assessment(self, modern_candidate):
        report = self.evaluator.evaluate(modern_candidate)

        assert report.overall_score >= 0
        assert report.overall_score <= 100

        # Modern Ubuntu should score higher
        assert report.overall_score >= 40

    def test_dimension_scores_present(self, legacy_candidate):
        report = self.evaluator.evaluate(legacy_candidate)

        dims = {ds.dimension.value: ds for ds in report.dimension_scores}
        assert "hardware_compatibility" in dims
        assert "software_support" in dims
        assert "config_complexity" in dims
        assert "security_baseline" in dims

    def test_scoring_weights(self, legacy_candidate):
        report = self.evaluator.evaluate(legacy_candidate)
        total_weight = sum(ds.weight for ds in report.dimension_scores)
        assert abs(total_weight - 1.0) < 0.01

    def test_issues_detected_for_legacy(self, legacy_candidate):
        report = self.evaluator.evaluate(legacy_candidate)
        # Legacy system should have issues
        assert len(report.issues) >= 1


class TestComplexityEvaluator:
    """Tests for complexity evaluation."""

    def setup_method(self):
        self.evaluator = ComplexityEvaluator()

    def test_legacy_complexity(self, legacy_candidate):
        result = self.evaluator.evaluate(legacy_candidate, detail_level="detailed")

        assert result.assessment.level is not None
        assert result.assessment.score >= 0
        assert result.assessment.estimated_effort_days is not None
        assert len(result.assessment.factors) > 0
        assert len(result.assessment.skill_requirements) > 0

    def test_modern_complexity_lower(self, legacy_candidate, modern_candidate):
        legacy_result = self.evaluator.evaluate(legacy_candidate)
        modern_result = self.evaluator.evaluate(modern_candidate)

        # Modern system should have lower complexity score
        # (Higher score = more complex)
        assert modern_result.assessment.score <= legacy_result.assessment.score or \
               modern_result.assessment.level.value <= legacy_result.assessment.level.value

    def test_resource_sizing(self, legacy_candidate):
        result = self.evaluator.evaluate(legacy_candidate)

        sizing = result.sizing
        assert sizing.cpu_cores > 0
        assert sizing.memory_gb > 0
        assert sizing.storage_gb > 0
        assert sizing.replicas >= 1
        assert sizing.rationale != ""

    def test_migration_strategy(self, legacy_candidate):
        result = self.evaluator.evaluate(legacy_candidate)

        strategy = result.strategy
        assert strategy.strategy_type != ""
        assert len(strategy.phases) > 0
        assert len(strategy.risks) > 0
        assert strategy.rollback_strategy != ""


class TestSecurityEvaluator:
    """Tests for security evaluation."""

    def setup_method(self):
        self.evaluator = SecurityEvaluator()

    def test_security_assessment(self, legacy_candidate):
        result = self.evaluator.evaluate(legacy_candidate)
        assert result.score >= 0
        assert result.level is not None
        assert result.breakdown != ""
