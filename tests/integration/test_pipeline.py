"""Integration tests for the full OpsMind pipeline."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from opsmind.core.engine import OpsMindEngine
from opsmind.reporting.generators.json import JSONReportGenerator
from opsmind.reporting.generators.markdown import MarkdownReportGenerator
from opsmind.remediation.generators.docker import DockerGenerator
from opsmind.remediation.generators.migration_plan import MigrationPlanGenerator
from opsmind.schemas.report import DetailLevel


@pytest.mark.integration
class TestFullPipeline:
    """Integration tests for the full OpsMind pipeline."""

    def setup_method(self):
        self.engine = OpsMindEngine()
        self.tmpdir = tempfile.mkdtemp(prefix="opsmind_test_")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_discover_to_assess_pipeline(self):
        """Test discovery -> assessment pipeline."""
        discovery = self.engine.discover("localhost", method="mock")
        assert discovery.total_hosts >= 1
        assert discovery.successful_hosts >= 1

        assessment = self.engine.assess(discovery)
        assert len(assessment) >= 1

        for hostname, result in assessment.items():
            assert 0 <= result.feasibility.overall_score <= 100
            assert result.migration_strategy.strategy_type != ""

    def test_discover_legacy_assess(self):
        """Test legacy system discovery and assessment."""
        discovery = self.engine.discover("legacy-centos", method="mock")
        assert discovery.total_hosts >= 1

        assessment = self.engine.assess(discovery)
        result = list(assessment.values())[0]

        # Legacy CentOS should have lower scores
        # The mock profile for centos should identify it
        assert result.feasibility.overall_score <= 80
        assert len(result.feasibility.issues) >= 1

    def test_markdown_report_generation(self):
        """Test Markdown report generation."""
        discovery = self.engine.discover("localhost", method="mock")
        assessment = self.engine.assess(discovery)

        generator = MarkdownReportGenerator(output_dir=self.tmpdir)
        report_data = generator.generate(assessment, DetailLevel.DETAILED)
        assert report_data is not None
        assert len(report_data.sections) > 0

        output_path = os.path.join(self.tmpdir, "test_report.md")
        generator.export(report_data, output_path)
        assert os.path.exists(output_path)

        with open(output_path) as f:
            content = f.read()
        assert "OpsMind" in content
        assert "# " in content  # Markdown headers

    def test_json_report_generation(self):
        """Test JSON report generation."""
        discovery = self.engine.discover("localhost", method="mock")
        assessment = self.engine.assess(discovery)

        generator = JSONReportGenerator(output_dir=self.tmpdir)
        report_data = generator.generate(assessment, DetailLevel.DETAILED)

        output_path = os.path.join(self.tmpdir, "test_report.json")
        generator.export(report_data, output_path)
        assert os.path.exists(output_path)

        with open(output_path) as f:
            data = json.load(f)
        assert "metadata" in data
        assert "hosts" in data
        assert "global_recommendations" in data

    def test_docker_artifacts_generation(self):
        """Test Docker artifact generation."""
        discovery = self.engine.discover("localhost", method="mock")
        assessment = self.engine.assess(discovery)

        generator = DockerGenerator(output_dir=self.tmpdir)
        files = generator.generate(assessment)

        assert len(files) >= 1

        dockerfile_paths = [f for f in files if "Dockerfile" in f]
        assert len(dockerfile_paths) >= 1

        compose_paths = [f for f in files if "docker-compose" in f]
        assert len(compose_paths) >= 1

    def test_migration_plan_generation(self):
        """Test migration plan generation."""
        discovery = self.engine.discover("localhost", method="mock")
        assessment = self.engine.assess(discovery)

        generator = MigrationPlanGenerator(output_dir=self.tmpdir)
        files = generator.generate(assessment)

        assert len(files) >= 2  # Per-host + overview

        for f in files:
            assert os.path.exists(f)
            with open(f) as fh:
                content = fh.read()
            assert "Migration" in content or "migration" in content

    def test_full_pipeline_with_remediation(self):
        """Test complete pipeline including remediation."""
        result = self.engine.run_pipeline(
            "localhost",
            method="mock",
            report_format="json",
            output_dir=self.tmpdir,
            generate_remediation=True,
        )

        assert "discovery" in result
        assert "assessment" in result
        assert "report" in result
        assert "remediation" in result
        assert "docker" in result["remediation"]
        assert "migration_plan" in result["remediation"]

    def test_multiple_host_pipeline(self):
        """Test pipeline with multiple mock hosts."""
        discovery = self.engine.discover("legacy-centos,modern-ubuntu", method="mock")
        assert discovery.total_hosts == 2
        assert discovery.successful_hosts == 2

        assessment = self.engine.assess(discovery)
        assert len(assessment) == 2

    def test_pipeline_events(self):
        """Test that pipeline emits expected events."""
        events = []

        def collector(event):
            events.append(event.type.value)

        # Subscribe to all event types
        from opsmind.core.events import EventType
        for et in EventType:
            self.engine.event_bus.subscribe(et, collector)

        self.engine.run_pipeline("localhost", method="mock")

        event_values = [e for e in events]
        assert "discovery.started" in event_values
        assert "discovery.completed" in event_values
        assert "assessment.started" in event_values
        assert "assessment.completed" in event_values
        assert "report.generation.started" in event_values
        assert "report.generation.completed" in event_values
