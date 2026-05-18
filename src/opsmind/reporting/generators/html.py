"""HTML report generator."""

import os
from datetime import datetime
from typing import Dict, List

from opsmind.reporting.generators.base import BaseReportGenerator
from opsmind.schemas.assessment import AssessmentResult, ComplexityLevel
from opsmind.schemas.report import DetailLevel, ReportData, ReportMetadata


class HTMLReportGenerator(BaseReportGenerator):
    """Generates HTML assessment reports with visual formatting."""

    def generate(
        self, assessment_results: Dict[str, AssessmentResult], detail_level: DetailLevel
    ) -> ReportData:
        """Generate HTML report data."""
        scores = [r.feasibility.overall_score for r in assessment_results.values()]
        avg_score = sum(scores) / len(scores) if scores else 0

        exec_summary = (
            f"Assessment of {len(assessment_results)} host(s). "
            f"Average feasibility score: {avg_score:.1f}/100."
        )

        metadata = ReportMetadata(
            title="OpsMind Containerization Assessment Report",
            generated_at=datetime.now(),
            tool_version="0.1.0",
            total_hosts=len(assessment_results),
        )

        return ReportData(
            metadata=metadata,
            executive_summary=exec_summary,
            assessment_summary={"average_score": round(avg_score, 1)},
            host_reports=assessment_results,
        )

    def export(self, report_data: ReportData, output_path: str) -> str:
        """Export report as self-contained HTML file."""
        html = self._build_html(report_data)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(html)

        return output_path

    def _build_html(self, report: ReportData) -> str:
        """Build complete HTML page."""
        host_cards = "\n".join(
            self._build_host_card(host, result)
            for host, result in report.host_reports.items()
        )

        avg_score = report.assessment_summary.get("average_score", 0)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.metadata.title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #0f172a; color: #e2e8f0; line-height: 1.6; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{ text-align: center; padding: 2rem 0; border-bottom: 1px solid #334155; margin-bottom: 2rem; }}
        h1 {{ font-size: 2rem; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .meta {{ color: #94a3b8; font-size: 0.9rem; margin-top: 0.5rem; }}
        .summary {{ background: #1e293b; border-radius: 1rem; padding: 1.5rem; margin-bottom: 2rem; }}
        .score-large {{ font-size: 3rem; font-weight: bold; color: #60a5fa; }}
        .host-card {{ background: #1e293b; border-radius: 1rem; padding: 1.5rem; margin-bottom: 1.5rem; }}
        .host-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }}
        .host-name {{ font-size: 1.3rem; font-weight: bold; color: #f1f5f9; }}
        .score {{ font-size: 1.2rem; font-weight: bold; }}
        .score-high {{ color: #22c55e; }} .score-mid {{ color: #eab308; }} .score-low {{ color: #ef4444; }}
        .dims {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1rem 0; }}
        .dim {{ background: #0f172a; border-radius: 0.5rem; padding: 1rem; }}
        .dim-name {{ color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; }}
        .dim-score {{ font-size: 1.4rem; font-weight: bold; }}
        .bar {{ height: 6px; background: #334155; border-radius: 3px; margin-top: 0.5rem; }}
        .bar-fill {{ height: 100%; border-radius: 3px; transition: width 0.5s; }}
        .issues {{ margin: 1rem 0; }}
        .issue {{ padding: 0.5rem; border-left: 3px solid; margin: 0.5rem 0; background: #0f172a; border-radius: 0 0.25rem 0.25rem 0; }}
        .issue-high {{ border-color: #ef4444; }} .issue-med {{ border-color: #eab308; }} .issue-low {{ border-color: #22c55e; }}
        .recs {{ list-style: none; }}
        .recs li {{ padding: 0.3rem 0; padding-left: 1rem; position: relative; }}
        .recs li::before {{ content: '▸'; position: absolute; left: 0; color: #60a5fa; }}
        .sizing {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; text-align: center; margin: 1rem 0; }}
        .sizing-item {{ background: #0f172a; border-radius: 0.5rem; padding: 0.75rem; }}
        .sizing-value {{ font-size: 1.5rem; font-weight: bold; color: #60a5fa; }}
        .sizing-label {{ font-size: 0.8rem; color: #94a3b8; }}
        footer {{ text-align: center; color: #475569; padding: 2rem; font-size: 0.85rem; }}
        .complexity-badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }}
        .c-simple {{ background: #22c55e20; color: #22c55e; border: 1px solid #22c55e40; }}
        .c-moderate {{ background: #eab30820; color: #eab308; border: 1px solid #eab30840; }}
        .c-complex {{ background: #f9731620; color: #f97316; border: 1px solid #f9731640; }}
        .c-blocker {{ background: #ef444420; color: #ef4444; border: 1px solid #ef444440; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{report.metadata.title}</h1>
            <div class="meta">
                Generated: {report.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')} |
                Version: {report.metadata.tool_version} |
                Hosts: {report.metadata.total_hosts}
            </div>
        </header>

        <div class="summary">
            <h2>Executive Summary</h2>
            <div class="score-large">{avg_score:.1f}</div>
            <div style="color: #94a3b8;">/ 100 - Overall Feasibility Score</div>
            <p style="margin-top: 1rem;">{report.executive_summary}</p>
        </div>

        {host_cards}

        <footer>
            Generated by OpsMind v{report.metadata.tool_version} |
            Report contains {report.metadata.total_hosts} host(s) |
            Assessment algorithm: opsmind-weighted-v1
        </footer>
    </div>
</body>
</html>"""

    def _build_host_card(self, hostname: str, result: AssessmentResult) -> str:
        """Build HTML for a single host assessment."""
        feas = result.feasibility
        comp = result.complexity
        sizing = result.resource_sizing

        score_class = "score-high" if feas.overall_score >= 70 else "score-mid" if feas.overall_score >= 40 else "score-low"
        complexity_map = {
            ComplexityLevel.SIMPLE: "c-simple",
            ComplexityLevel.MODERATE: "c-moderate",
            ComplexityLevel.COMPLEX: "c-complex",
            ComplexityLevel.BLOCKER: "c-blocker",
        }
        badge_class = complexity_map.get(feas.complexity, "c-moderate")

        dim_cards = ""
        for ds in feas.dimension_scores:
            bar_color = "#22c55e" if ds.score >= 70 else "#eab308" if ds.score >= 40 else "#ef4444"
            dim_cards += f"""
            <div class="dim">
                <div class="dim-name">{ds.dimension.value.replace('_', ' ')}</div>
                <div class="dim-score" style="color: {bar_color}">{ds.score:.0f}</div>
                <div class="bar"><div class="bar-fill" style="width: {ds.score}%; background: {bar_color};"></div></div>
            </div>"""

        issues_html = ""
        for issue in feas.issues[:5]:
            sev_class = f"issue-{issue.severity.value}"
            issues_html += f'<div class="issue {sev_class}">{issue.title}</div>'

        recs_html = "\n".join(f"<li>{r}</li>" for r in feas.recommendations[:5])

        sizing_html = f"""
        <div class="sizing">
            <div class="sizing-item"><div class="sizing-value">{sizing.cpu_cores}</div><div class="sizing-label">CPU Cores</div></div>
            <div class="sizing-item"><div class="sizing-value">{sizing.memory_gb}</div><div class="sizing-label">Memory (GB)</div></div>
            <div class="sizing-item"><div class="sizing-value">{sizing.storage_gb}</div><div class="sizing-label">Storage (GB)</div></div>
        </div>"""

        return f"""
        <div class="host-card">
            <div class="host-header">
                <div>
                    <span class="host-name">{hostname}</span>
                    <span class="complexity-badge {badge_class}" style="margin-left: 0.5rem;">{feas.complexity.value.upper()}</span>
                    <span style="color:#94a3b8;font-size:0.85rem;margin-left:0.5rem;">Risk: {feas.risk_level.value}</span>
                </div>
                <div class="score {score_class}">{feas.overall_score:.0f}/100</div>
            </div>

            <p style="color: #94a3b8; margin-bottom: 1rem;">{feas.summary}</p>

            <div class="dims">{dim_cards}</div>

            <h3 style="margin: 1rem 0 0.5rem;">Issues</h3>
            <div class="issues">{issues_html or '<p style="color:#22c55e;">No significant issues found.</p>'}</div>

            <h3 style="margin: 1rem 0 0.5rem;">Resource Sizing</h3>
            {sizing_html}

            <h3 style="margin: 1rem 0 0.5rem;">Recommendations</h3>
            <ul class="recs">{recs_html}</ul>

            <div style="margin-top: 0.5rem; color: #64748b; font-size: 0.85rem;">
                Strategy: {result.migration_strategy.strategy_type} |
                Effort: {comp.estimated_effort_days} days |
                Source: {result.data_source}
            </div>
        </div>"""
