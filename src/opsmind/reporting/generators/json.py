"""JSON report generator."""

import json
import os
from datetime import datetime

from opsmind import __version__
from opsmind.reporting.generators.base import BaseReportGenerator
from opsmind.schemas.assessment import AssessmentResult
from opsmind.schemas.report import DetailLevel, ReportData, ReportMetadata


class JSONReportGenerator(BaseReportGenerator):
    """Generates JSON assessment reports for programmatic consumption."""

    def generate(self, assessment_results: dict[str, AssessmentResult], detail_level: DetailLevel) -> ReportData:
        """Generate JSON report data."""
        host_data = {}
        for hostname, result in assessment_results.items():
            host_data[hostname] = self._result_to_dict(result)

        scores = [r.feasibility.overall_score for r in assessment_results.values()]
        avg_score = sum(scores) / len(scores) if scores else 0

        exec_summary = (
            f"Assessment of {len(assessment_results)} host(s). Average feasibility score: {avg_score:.1f}/100."
        )

        recommendations = []
        for result in assessment_results.values():
            recommendations.extend(result.feasibility.recommendations)

        metadata = ReportMetadata(
            title="OpsMind Assessment Report (JSON)",
            generated_at=datetime.now(),
            tool_version=__version__,
            total_hosts=len(assessment_results),
        )

        return ReportData(
            metadata=metadata,
            executive_summary=exec_summary,
            assessment_summary={
                "average_score": round(avg_score, 1),
                "total_hosts": len(assessment_results),
            },
            host_reports=assessment_results,
            global_recommendations=list(dict.fromkeys(recommendations)),
        )

    def export(self, report_data: ReportData, output_path: str) -> str:
        """Export report as JSON file."""
        data = {
            "metadata": {
                "title": report_data.metadata.title,
                "generated_at": report_data.metadata.generated_at.isoformat(),
                "tool_version": report_data.metadata.tool_version,
                "total_hosts": report_data.metadata.total_hosts,
            },
            "executive_summary": report_data.executive_summary,
            "assessment_summary": report_data.assessment_summary,
            "hosts": {host: self._result_to_dict(result) for host, result in report_data.host_reports.items()},
            "global_recommendations": report_data.global_recommendations,
            "generated_files": report_data.generated_files,
        }

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        return output_path

    def _result_to_dict(self, result: AssessmentResult) -> dict[str, object]:
        """Convert AssessmentResult to a JSON-serializable dict."""
        return {
            "host": result.host,
            "data_source": result.data_source,
            "assessed_at": result.assessed_at.isoformat(),
            "feasibility": {
                "overall_score": result.feasibility.overall_score,
                "complexity": result.feasibility.complexity.value,
                "risk_level": result.feasibility.risk_level.value,
                "summary": result.feasibility.summary,
                "dimension_scores": [
                    {
                        "dimension": ds.dimension.value,
                        "score": ds.score,
                        "weight": ds.weight,
                        "findings": ds.findings,
                        "issues": ds.issues,
                        "recommendations": ds.recommendations,
                    }
                    for ds in result.feasibility.dimension_scores
                ],
                "issues": [
                    {
                        "category": i.category,
                        "severity": i.severity.value,
                        "title": i.title,
                        "description": i.description,
                    }
                    for i in result.feasibility.issues
                ],
                "recommendations": result.feasibility.recommendations,
            },
            "complexity": {
                "level": result.complexity.level.value,
                "score": result.complexity.score,
                "estimated_effort_days": result.complexity.estimated_effort_days,
                "skill_requirements": result.complexity.skill_requirements,
            },
            "resource_sizing": {
                "cpu_cores": result.resource_sizing.cpu_cores,
                "memory_gb": result.resource_sizing.memory_gb,
                "storage_gb": result.resource_sizing.storage_gb,
                "replicas": result.resource_sizing.replicas,
                "rationale": result.resource_sizing.rationale,
            },
            "migration_strategy": {
                "strategy_type": result.migration_strategy.strategy_type,
                "estimated_duration_days": result.migration_strategy.estimated_duration_days,
                "risks": result.migration_strategy.risks,
            },
        }
