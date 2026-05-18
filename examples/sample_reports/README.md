# Sample Reports

This directory contains example OpsMind assessment reports.

## Generating Reports

Run the demo to generate sample reports:

```bash
# Quick demo
bash examples/demo_scripts/quick_demo.sh

# Full pipeline
bash examples/demo_scripts/full_pipeline.sh

# Interactive Python demo
python examples/demo_scripts/interactive_demo.py
```

## Report Formats

### Markdown (`opsmind_report.md`)
- Human-readable with structured sections
- Executive summary, per-host analysis, recommendations
- Methodology transparency section

### JSON (`opsmind_report.json`)
- Machine-parseable for programmatic consumption
- Complete data structure for custom tooling
- Suitable for CI/CD pipeline integration

### HTML (`opsmind_report.html`)
- Self-contained visual report
- Inline CSS (no external dependencies)
- Color-coded scores and progress bars
- Mobile-responsive design

## Report Contents

Every OpsMind report includes:

1. **Executive Summary**: Overall feasibility score and host overview
2. **Per-Host Analysis**: Dimension scores, issues, recommendations
3. **Resource Sizing**: Recommended CPU/Memory/Storage for containers
4. **Migration Strategy**: Recommended approach with phases and risks
5. **Methodology**: Transparent scoring methodology and data sources
6. **Action Items**: Prioritized checklist for modernization
