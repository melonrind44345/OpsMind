"""Markdown report generator."""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from opsmind.reporting.generators.base import BaseReportGenerator
from opsmind.schemas.assessment import AssessmentResult, ComplexityLevel, DimensionScore, RiskLevel
from opsmind.schemas.report import DetailLevel, ReportData, ReportMetadata, ReportSection


class MarkdownReportGenerator(BaseReportGenerator):
    """Generates Markdown assessment reports."""

    def generate(
        self, assessment_results: Dict[str, AssessmentResult], detail_level: DetailLevel
    ) -> ReportData:
        """Generate a Markdown report."""
        sections: List[ReportSection] = []

        # Title section
        sections.append(self._generate_title_section(assessment_results))

        # Executive summary
        exec_summary = self._generate_executive_summary(assessment_results)
        sections.append(ReportSection(
            title="Executive Summary",
            content=exec_summary,
        ))

        # Per-host sections
        for hostname, result in assessment_results.items():
            host_section = self._generate_host_section(hostname, result, detail_level)
            sections.append(host_section)

        # Global recommendations
        recommendations = self._collect_recommendations(assessment_results)
        if recommendations:
            recs_content = "\n".join(f"- {r}" for r in recommendations)
            sections.append(ReportSection(
                title="Recommendations",
                content=recs_content,
            ))

        # Methodology
        sections.append(self._generate_methodology_section())

        report_data = ReportData(
            metadata=ReportMetadata(
                title="OpsMind Containerization Assessment Report",
                generated_at=datetime.now(),
                tool_version="0.1.0",
                total_hosts=len(assessment_results),
            ),
            executive_summary=exec_summary,
            sections=sections,
            global_recommendations=recommendations,
        )

        return report_data

    def export(self, report_data: ReportData, output_path: str) -> str:
        """Export report to Markdown file."""
        lines: List[str] = []

        lines.append(f"# {report_data.metadata.title}")
        lines.append("")
        lines.append(f"*Generated: {report_data.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append(f"*Tool Version: {report_data.metadata.tool_version}*")
        lines.append(f"*Hosts Assessed: {report_data.metadata.total_hosts}*")
        lines.append("")
        lines.append("---")
        lines.append("")

        for section in report_data.sections:
            lines.append(f"## {section.title}")
            lines.append("")
            lines.append(section.content)
            lines.append("")
            if section.subsections:
                for sub in section.subsections:
                    lines.append(f"### {sub.title}")
                    lines.append("")
                    lines.append(sub.content)
                    lines.append("")
            lines.append("---")
            lines.append("")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write("\n".join(lines))

        return output_path

    def _generate_title_section(self, results: Dict[str, AssessmentResult]) -> ReportSection:
        """Generate title and overview section."""
        scores = [r.feasibility.overall_score for r in results.values()]
        avg_score = sum(scores) / len(scores) if scores else 0

        host_list = "\n".join(
            f"  - **{h}**: {r.feasibility.overall_score:.1f}/100 ({r.feasibility.complexity.value})"
            for h, r in results.items()
        )

        content = (
            f"**Overall Score**: {avg_score:.1f}/100\n\n"
            f"**Hosts Assessed**:\n{host_list}"
        )

        return ReportSection(title="Overview", content=content)

    def _generate_executive_summary(self, results: Dict[str, AssessmentResult]) -> str:
        """Generate executive summary."""
        scores = [r.feasibility.overall_score for r in results.values()]
        avg_score = sum(scores) / len(scores) if scores else 0

        simple = sum(1 for r in results.values() if r.feasibility.complexity == ComplexityLevel.SIMPLE)
        moderate = sum(1 for r in results.values() if r.feasibility.complexity == ComplexityLevel.MODERATE)
        complex_count = sum(1 for r in results.values() if r.feasibility.complexity == ComplexityLevel.COMPLEX)
        blocker = sum(1 for r in results.values() if r.feasibility.complexity == ComplexityLevel.BLOCKER)

        return (
            f"This report assesses **{len(results)} host(s)** for containerization readiness.\n\n"
            f"**Overall Feasibility Score**: {avg_score:.1f}/100\n\n"
            f"**Complexity Distribution**:\n"
            f"  - Simple: {simple}\n"
            f"  - Moderate: {moderate}\n"
            f"  - Complex: {complex_count}\n"
            f"  - Blocker: {blocker}\n\n"
            f"This assessment was performed using OpsMind v0.1.0 with data "
            f"collected via Ansible discovery. Each host is evaluated across "
            f"four dimensions: hardware compatibility, software support, "
            f"configuration complexity, and security baseline."
        )

    def _generate_host_section(
        self, hostname: str, result: AssessmentResult, detail_level: DetailLevel
    ) -> ReportSection:
        """Generate per-host report section."""
        feas = result.feasibility
        comp = result.complexity
        sizing = result.resource_sizing

        lines = [
            f"### Score: {feas.overall_score:.1f}/100",
            f"**Complexity**: {feas.complexity.value.upper()}",
            f"**Risk Level**: {feas.risk_level.value.upper()}",
            f"**Data Source**: {result.data_source}",
            "",
            "---",
            "",
            feas.summary,
            "",
            "#### Dimension Scores",
            "",
        ]

        for ds in feas.dimension_scores:
            bar = self._score_bar(ds.score)
            lines.append(f"- **{ds.dimension.value.replace('_', ' ').title()}**: {ds.score:.1f}/100 {bar}")
            if ds.findings:
                for f_text in ds.findings:
                    lines.append(f"  - {f_text}")

        lines.append("")
        lines.append("#### Issues Found")
        lines.append("")

        if feas.issues:
            for issue in feas.issues:
                lines.append(f"- **[{issue.severity.upper()}]** {issue.title}")
                lines.append(f"  - {issue.description}")
        else:
            lines.append("No significant issues found.")

        lines.append("")
        lines.append("#### Resource Sizing Recommendation")
        lines.append("")
        lines.append(f"- CPU: {sizing.cpu_cores} cores")
        lines.append(f"- Memory: {sizing.memory_gb} GB")
        lines.append(f"- Storage: {sizing.storage_gb} GB")
        lines.append(f"- Replicas: {sizing.replicas}")
        lines.append(f"- Rationale: {sizing.rationale}")
        if sizing.optimizations:
            for opt in sizing.optimizations:
                lines.append(f"  - Optimization: {opt}")

        lines.append("")
        lines.append("#### Migration Strategy")
        lines.append("")
        lines.append(f"- **Strategy**: {result.migration_strategy.strategy_type}")
        lines.append(f"- **Estimated Effort**: {comp.estimated_effort_days} days")
        phases_table = "\n".join(
            f"  - Phase {p.get('phase', i+1)}: {p.get('name', '')} ({p.get('duration', '')})"
            for i, p in enumerate(result.migration_strategy.phases)
        )
        lines.append(f"- **Phases**:\n{phases_table}")
        if result.migration_strategy.risks:
            lines.append("- **Risks**:")
            for risk in result.migration_strategy.risks:
                lines.append(f"  - {risk}")

        if detail_level == DetailLevel.DETAILED:
            lines.append("")
            lines.append("#### Required Skills")
            lines.append("")
            for skill in comp.skill_requirements:
                lines.append(f"- {skill}")

        return ReportSection(
            title=f"Host: {hostname}",
            content="\n".join(lines),
        )

    def _collect_recommendations(self, results: Dict[str, AssessmentResult]) -> List[str]:
        """Collect global recommendations."""
        all_recs: List[str] = []
        for result in results.values():
            all_recs.extend(result.feasibility.recommendations)
        # Deduplicate
        seen = set()
        unique = []
        for r in all_recs:
            if r not in seen:
                seen.add(r)
                unique.append(r)
        return unique[:10]

    def _generate_methodology_section(self) -> ReportSection:
        """Generate methodology transparency section."""
        content = (
            "This assessment uses the **OpsMind Weighted Evaluation Algorithm v1**.\n\n"
            "**Scoring Dimensions**:\n"
            "- **Hardware Compatibility (30%)**: CPU architecture, cores, memory, disk space\n"
            "- **Software Support (30%)**: OS type/version, kernel, package ecosystem\n"
            "- **Configuration Complexity (20%)**: Services, dependencies, mount points\n"
            "- **Security Baseline (20%)**: Firewall, SELinux, pending updates\n\n"
            "**Data Sources**:\n"
            "- Ansible `setup` module facts (primary)\n"
            "- Native system detection (fallback)\n"
            "- Mock/demo data (if specified)\n\n"
            "**Confidence Levels**:\n"
            "- HIGH: Direct Ansible/native measurement\n"
            "- LOW: Inferred or heuristic data\n"
            "- ESTIMATED: Best-guess when data unavailable"
        )
        return ReportSection(title="Methodology", content=content)

    @staticmethod
    def _score_bar(score: float) -> str:
        """Generate a simple text bar for scores."""
        filled = int(score / 10)
        return "█" * filled + "░" * (10 - filled)
