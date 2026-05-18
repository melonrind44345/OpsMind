#!/bin/bash
# OpsMind Full Pipeline Demo
# Complete workflow: discovery -> assessment -> reporting -> remediation
set -euo pipefail

OUTPUT_DIR="./opsmind_full_demo"
mkdir -p "$OUTPUT_DIR"

echo "═══════════════════════════════════════════════════"
echo "  OpsMind Full Pipeline Demo"
echo "  Complete Modernization Assessment Workflow"
echo "═══════════════════════════════════════════════════"

# Clean up from previous runs
rm -f "$OUTPUT_DIR"/*.md "$OUTPUT_DIR"/*.json > /dev/null 2>&1 || true

# 1. Discover multiple mock systems
echo ""
echo "▶ Phase 1: Multi-System Discovery"
echo "----------------------------------------"
opsmind discover "legacy-centos,modern-ubuntu" \
    --method mock \
    --output "$OUTPUT_DIR/discovery_results.json"
echo ""

# 2. Full assessment
echo "▶ Phase 2: Full Assessment"
echo "----------------------------------------"
opsmind assess --report-format json --output "$OUTPUT_DIR/assessment.json"
echo ""

# 3. Generate all report formats
echo "▶ Phase 3: Multi-Format Reports"
echo "----------------------------------------"
opsmind report export --format markdown --output "$OUTPUT_DIR/report.md"
opsmind report export --format json --output "$OUTPUT_DIR/report.json"
opsmind report export --format html --output "$OUTPUT_DIR/report.html"
echo "  ✓ Markdown: $OUTPUT_DIR/report.md"
echo "  ✓ JSON: $OUTPUT_DIR/report.json"
echo "  ✓ HTML: $OUTPUT_DIR/report.html"
echo ""

# 4. Generate remediation artifacts
echo "▶ Phase 4: Remediation Artifacts"
echo "----------------------------------------"
opsmind generate docker --output-dir "$OUTPUT_DIR/artifacts" --optimize performance
opsmind generate migration-plan --output-dir "$OUTPUT_DIR/artifacts"
echo ""

# 5. Validate results
echo "▶ Phase 5: Results Summary"
echo "----------------------------------------"
echo ""
echo "Generated Files:"
find "$OUTPUT_DIR" -type f | sort | while read -r f; do
    size=$(du -h "$f" | cut -f1)
    echo "  📄 $f ($size)"
done

echo ""
echo "═══ Demo Complete ═══"
echo ""
echo "The full pipeline demonstrates OpsMind's ability to:"
echo "  • Discover legacy and modern systems simultaneously"
echo "  • Evaluate containerization feasibility with transparent scoring"
echo "  • Generate professional reports in multiple formats"
echo "  • Create actionable Docker and migration artifacts"
echo ""
echo "Next: Review $OUTPUT_DIR/report.html in your browser"
echo "      Check $OUTPUT_DIR/artifacts/plans/ for migration plans"
