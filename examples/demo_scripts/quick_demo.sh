#!/bin/bash
# OpsMind Quick Demo Script
# Showcases core capabilities in under 2 minutes
set -euo pipefail

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║        OpsMind v0.1.0 - Quick Demo               ║"
echo "║  Ansible-Driven Modernization Platform            ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# Step 1: Validate setup
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 1: System Validation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
opsmind validate
echo ""

# Step 2: Discover a legacy system (mock)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 2: Discover Legacy CentOS 6 System"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
opsmind discover legacy-centos --method mock
echo ""

# Step 3: Assess and generate report
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 3: Containerization Assessment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
opsmind assess --report-format markdown --output opsmind_quick_report.md
echo ""

# Step 4: Generate Docker artifacts
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 4: Generate Docker Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
opsmind generate docker --output-dir opsmind_artifacts
echo ""

# Step 5: Generate migration plan
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 5: Generate Migration Plan"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
opsmind generate migration-plan --output-dir opsmind_artifacts
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Demo Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Generated artifacts:"
echo "  📄 opsmind_quick_report.md"
echo "  📁 opsmind_artifacts/"
echo "      └── docker/legacy-app-01/"
echo "          ├── Dockerfile"
echo "          ├── docker-compose.yml"
echo "          ├── .dockerignore"
echo "          └── build.sh"
echo "      └── plans/"
echo "          ├── 00_migration_overview.md"
echo "          └── legacy-app-01_migration_plan.md"
echo ""
echo "Next steps:"
echo "  • Run 'opsmind discover localhost' for real system discovery"
echo "  • Run 'opsmind pipeline <target>' for full automated workflow"
echo "  • Check opsmind_quick_report.md for detailed assessment"
echo ""
