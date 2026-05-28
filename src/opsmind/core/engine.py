"""Main OpsMind engine - orchestrates the discovery, assessment, reporting, remediation workflow."""

import time
from typing import Any

from opsmind.core.events import Event, EventBus, EventType
from opsmind.core.exceptions import (
    AssessmentError,
    DiscoveryError,
    RemediationError,
    ReportGenerationError,
)
from opsmind.discovery.engines.base import BaseDiscoveryEngine
from opsmind.schemas.assessment import AssessmentResult
from opsmind.schemas.discovery import DiscoveryMethod, DiscoveryResult
from opsmind.schemas.report import DetailLevel, ReportData, ReportFormat


class OpsMindEngine:
    """Central orchestrator for the OpsMind workflow.

    Coordinates discovery -> assessment -> reporting -> remediation pipeline.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.event_bus = EventBus()
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default event logging handlers."""
        self.event_bus.subscribe(EventType.WORKFLOW_STEP, self._log_event)
        self.event_bus.subscribe(EventType.WARNING, self._log_event)
        self.event_bus.subscribe(EventType.ERROR, self._log_event)

    def _log_event(self, event: Event) -> None:
        """Default event logger."""
        pass  # Override to integrate with logging system

    def discover(
        self,
        target: str,
        method: str = "auto",
        inventory: str | None = None,
        ssh_user: str | None = None,
        ssh_key: str | None = None,
        parallel: bool = True,
    ) -> DiscoveryResult:
        """Execute discovery on target host(s).

        Args:
            target: Hostname, IP, or inventory group
            method: Discovery method ('ansible', 'native', 'mock', 'auto')
            inventory: Path to Ansible inventory file
            ssh_user: SSH username for remote hosts
            ssh_key: SSH private key path
            parallel: Whether to discover hosts in parallel

        Returns:
            DiscoveryResult with collected data
        """
        from opsmind.discovery.engines.ansible_engine import AnsibleDiscoveryEngine
        from opsmind.discovery.engines.mock_engine import MockDiscoveryEngine
        from opsmind.discovery.engines.native_engine import NativeDiscoveryEngine

        self._validate_target(target)
        method_enum = self._resolve_method(method)

        self.event_bus.emit_simple(EventType.DISCOVERY_STARTED, {"target": target, "method": method_enum.value})

        if method_enum == DiscoveryMethod.AUTO:
            engine = self._select_engine(target, inventory, ssh_user, ssh_key)
        elif method_enum == DiscoveryMethod.ANSIBLE:
            engine = AnsibleDiscoveryEngine(
                inventory_path=inventory,
                ssh_config={"user": ssh_user, "key_file": ssh_key},
            )
        elif method_enum == DiscoveryMethod.NATIVE:
            engine = NativeDiscoveryEngine()
        elif method_enum == DiscoveryMethod.MOCK:
            engine = MockDiscoveryEngine()
        else:
            raise DiscoveryError(f"Unknown discovery method: {method}")

        start_time = time.time()

        try:
            if target == "localhost":
                result = engine.discover_host("localhost")
            elif "," in target:
                hosts = [h.strip() for h in target.split(",")]
                result = engine.discover_group(hosts, parallel=parallel)
            else:
                result = engine.discover_host(target)
        except Exception as exc:
            self.event_bus.emit_simple(EventType.DISCOVERY_HOST_FAILED, {"target": target, "error": str(exc)})
            raise DiscoveryError(f"Discovery failed for {target}: {exc}", details={"target": target}) from exc

        duration = (time.time() - start_time) * 1000
        result.total_duration_ms = duration

        self.event_bus.emit_simple(
            EventType.DISCOVERY_COMPLETED,
            {
                "target": target,
                "duration_ms": duration,
                "hosts": result.total_hosts,
            },
        )

        return result

    def assess(self, discovery_result: DiscoveryResult, detail_level: str = "detailed") -> dict[str, AssessmentResult]:
        """Assess discovery results for containerization feasibility.

        Args:
            discovery_result: Result from discover()
            detail_level: Assessment detail level

        Returns:
            Dict of host -> AssessmentResult
        """
        from opsmind.assessment.evaluators.complexity import ComplexityEvaluator
        from opsmind.assessment.evaluators.feasibility import ContainerizationFeasibilityEvaluator
        from opsmind.assessment.evaluators.security import SecurityEvaluator

        self.event_bus.emit_simple(
            EventType.ASSESSMENT_STARTED,
            {
                "hosts": list(discovery_result.hosts.keys()),
            },
        )

        feasibility = ContainerizationFeasibilityEvaluator()
        complexity = ComplexityEvaluator()
        security = SecurityEvaluator()

        results: dict[str, AssessmentResult] = {}

        for hostname, host_data in discovery_result.hosts.items():
            try:
                feas_report = feasibility.evaluate(host_data)
                comp_report = complexity.evaluate(host_data, detail_level=detail_level)
                security.evaluate(host_data)

                results[hostname] = AssessmentResult(
                    host=hostname,
                    feasibility=feas_report,
                    complexity=comp_report.assessment,
                    resource_sizing=comp_report.sizing,
                    migration_strategy=comp_report.strategy,
                    data_source=host_data.metadata.source.value,
                )
            except Exception as exc:
                raise AssessmentError(f"Assessment failed for {hostname}: {exc}") from exc

        self.event_bus.emit_simple(
            EventType.ASSESSMENT_COMPLETED,
            {
                "hosts": len(results),
            },
        )

        return results

    def generate_report(
        self,
        assessment_results: dict[str, AssessmentResult],
        format: str = "markdown",
        detail_level: str = "detailed",
        output_dir: str | None = None,
    ) -> ReportData:
        """Generate assessment report.

        Args:
            assessment_results: Results from assess()
            format: Output format (markdown, json, html)
            detail_level: Report detail level
            output_dir: Output directory path

        Returns:
            ReportData containing the report
        """
        import os

        from opsmind.reporting.generators.base import BaseReportGenerator
        from opsmind.reporting.generators.html import HTMLReportGenerator
        from opsmind.reporting.generators.json import JSONReportGenerator
        from opsmind.reporting.generators.markdown import MarkdownReportGenerator

        self.event_bus.emit_simple(EventType.REPORT_GENERATION_STARTED, {"format": format})

        detail = DetailLevel(detail_level)
        report_fmt = ReportFormat(format)

        generators: dict[ReportFormat, type[BaseReportGenerator]] = {
            ReportFormat.MARKDOWN: MarkdownReportGenerator,
            ReportFormat.JSON: JSONReportGenerator,
            ReportFormat.HTML: HTMLReportGenerator,
        }

        gen_cls = generators.get(report_fmt)
        if gen_cls is None:
            raise ReportGenerationError(f"Unsupported report format: {format}")

        generator = gen_cls(output_dir=output_dir)

        try:
            report_data = generator.generate(assessment_results, detail_level=detail)
        except Exception as exc:
            raise ReportGenerationError(f"Report generation failed: {exc}") from exc

        output_dir = output_dir or os.getcwd()
        output_path = os.path.join(output_dir, f"opsmind_report.{format}")
        generator.export(report_data, output_path)

        self.event_bus.emit_simple(
            EventType.REPORT_GENERATION_COMPLETED,
            {
                "format": format,
                "path": output_path,
            },
        )

        return report_data

    def generate_remediation(
        self,
        assessment_results: dict[str, AssessmentResult],
        output_dir: str | None = None,
        optimize: str | None = None,
    ) -> dict[str, list[str]]:
        """Generate remediation artifacts.

        Args:
            assessment_results: Results from assess()
            output_dir: Output directory path
            optimize: Optimization target (performance, size, cost)

        Returns:
            Dict of artifact type -> list of generated file paths
        """
        import os

        from opsmind.remediation.generators.docker import DockerGenerator
        from opsmind.remediation.generators.migration_plan import MigrationPlanGenerator

        self.event_bus.emit_simple(EventType.REMEDIATION_STARTED, {})

        output_dir = output_dir or os.getcwd()
        artifacts: dict[str, list[str]] = {}

        try:
            docker_gen = DockerGenerator(output_dir=output_dir)
            docker_files = docker_gen.generate(assessment_results, optimize=optimize)
            artifacts["docker"] = docker_files

            migration_gen = MigrationPlanGenerator(output_dir=output_dir)
            migration_plan = migration_gen.generate(assessment_results)
            artifacts["migration_plan"] = migration_plan
        except Exception as exc:
            raise RemediationError(f"Remediation generation failed: {exc}") from exc

        self.event_bus.emit_simple(
            EventType.REMEDIATION_COMPLETED,
            {
                "artifacts": artifacts,
            },
        )

        return artifacts

    def run_pipeline(
        self,
        target: str,
        method: str = "auto",
        report_format: str = "markdown",
        detail_level: str = "detailed",
        output_dir: str | None = None,
        generate_remediation: bool = False,
        optimize: str | None = None,
    ) -> dict[str, Any]:
        """Run the full discovery -> assessment -> reporting pipeline.

        Args:
            target: Target host(s) to discover
            method: Discovery method
            report_format: Output report format
            detail_level: Report detail level
            output_dir: Output directory
            generate_remediation: Whether to generate remediation artifacts
            optimize: Optimization target for remediation

        Returns:
            Dict with keys: discovery, assessment, report, (remediation)
        """
        self.event_bus.emit_simple(EventType.WORKFLOW_STEP, {"step": "pipeline_start", "target": target})

        discovery_result = self.discover(target, method=method)
        self.event_bus.emit_simple(EventType.WORKFLOW_STEP, {"step": "discovery_complete"})

        assessment_results = self.assess(discovery_result, detail_level=detail_level)
        self.event_bus.emit_simple(EventType.WORKFLOW_STEP, {"step": "assessment_complete"})

        report_data = self.generate_report(
            assessment_results,
            format=report_format,
            detail_level=detail_level,
            output_dir=output_dir,
        )
        self.event_bus.emit_simple(EventType.WORKFLOW_STEP, {"step": "report_complete"})

        result: dict[str, Any] = {
            "discovery": discovery_result,
            "assessment": assessment_results,
            "report": report_data,
        }

        if generate_remediation:
            artifacts = self.generate_remediation(assessment_results, output_dir=output_dir, optimize=optimize)
            result["remediation"] = artifacts

        self.event_bus.emit_simple(EventType.WORKFLOW_STEP, {"step": "pipeline_complete"})

        return result

    def _validate_target(self, target: str) -> None:
        """Validate the target specification."""
        if not target or not target.strip():
            raise DiscoveryError("Target cannot be empty")
        if len(target) > 1024:
            raise DiscoveryError("Target specification too long")

    def _resolve_method(self, method: str) -> DiscoveryMethod:
        """Resolve the discovery method string to enum."""
        try:
            return DiscoveryMethod(method.lower())
        except ValueError:
            raise DiscoveryError(f"Invalid discovery method: {method}. Use: ansible, native, mock, auto")

    def _select_engine(
        self, target: str, inventory: str | None, ssh_user: str | None, ssh_key: str | None
    ) -> BaseDiscoveryEngine:
        """Auto-select the best available engine."""
        from opsmind.discovery.engines.ansible_engine import AnsibleDiscoveryEngine
        from opsmind.discovery.engines.mock_engine import MockDiscoveryEngine
        from opsmind.discovery.engines.native_engine import NativeDiscoveryEngine

        if target == "localhost":
            engine = AnsibleDiscoveryEngine(
                inventory_path=inventory,
                ssh_config={"user": ssh_user, "key_file": ssh_key},
            )
            if engine.is_available:
                self.event_bus.emit_simple(
                    EventType.INFO,
                    {"engine": "ansible", "reason": "Ansible available for localhost"},
                )
                return engine

            native = NativeDiscoveryEngine()
            self.event_bus.emit_simple(EventType.ENGINE_FALLBACK, {"from": "ansible", "to": "native"})
            return native

        engine = AnsibleDiscoveryEngine(
            inventory_path=inventory,
            ssh_config={"user": ssh_user, "key_file": ssh_key},
        )
        if engine.is_available:
            return engine

        mock = MockDiscoveryEngine()
        self.event_bus.emit_simple(
            EventType.ENGINE_FALLBACK,
            {
                "from": "ansible",
                "to": "mock",
                "reason": "Ansible not available for remote discovery",
            },
        )
        return mock
