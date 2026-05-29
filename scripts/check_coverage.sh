#!/usr/bin/env bash
# =============================================================================
# Local coverage check — mirrors the CI coverage job behaviour.
# Usage:  ./scripts/check_coverage.sh [threshold]
#         ./scripts/check_coverage.sh 50   # fail if coverage < 50%
# =============================================================================
set -euo pipefail

THRESHOLD="${1:-48}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "======================================"
echo " OpsMind Coverage Check"
echo "======================================"
echo ""

# ------------------------------------------------------------------
# 1. Run unit tests with coverage
# ------------------------------------------------------------------
echo "[1/3] Running unit tests with coverage..."
python -m pytest tests/unit/ \
  -v --tb=short \
  -m "not ansible" \
  --cov=opsmind \
  --cov-report=xml:coverage-unit.xml \
  --cov-report=term \
  --no-header \
  2>&1 | tail -5

# ------------------------------------------------------------------
# 2. Run integration tests with coverage (append mode)
# ------------------------------------------------------------------
echo ""
echo "[2/3] Running integration tests with coverage (append)..."
python -m pytest tests/integration/ \
  -v --tb=long \
  --cov=opsmind \
  --cov-append \
  --cov-report=xml:coverage-integration.xml \
  --cov-report=term \
  --no-header \
  2>&1 | tail -5

# ------------------------------------------------------------------
# 3. Generate combined HTML report & threshold check
# ------------------------------------------------------------------
echo ""
echo "[3/3] Generating HTML coverage report..."
python -m coverage html -d htmlcov
python -m coverage json -o coverage.json

# Read metrics from JSON
COV_PCT=$(python -c "import json; print(json.load(open('coverage.json'))['totals']['percent_covered'])")
NUM_STMTS=$(python -c "import json; print(json.load(open('coverage.json'))['totals']['num_statements'])")
NUM_MISS=$(python -c "import json; print(json.load(open('coverage.json'))['totals']['num_missing'])")

echo ""
echo "======================================"
echo " Coverage Report"
echo "======================================"
printf "  %-20s %s\n" "Statements:" "$NUM_STMTS"
printf "  %-20s %s\n" "Covered:" "$((NUM_STMTS - NUM_MISS))"
printf "  %-20s %s\n" "Missing:" "$NUM_MISS"
printf "  %-20s %.1f%%\n" "Coverage:" "$COV_PCT"
printf "  %-20s %.0f%%\n" "Threshold:" "$THRESHOLD"

# Threshold check
if awk "BEGIN {exit !($COV_PCT >= $THRESHOLD)}"; then
  printf "  %-20s %s\n" "Status:" "✅ PASS"
  echo ""
  echo "HTML report: file://${PROJECT_ROOT}/htmlcov/index.html"
  exit 0
else
  printf "  %-20s %s\n" "Status:" "❌ FAIL (coverage ${COV_PCT}% < threshold ${THRESHOLD}%)"
  echo ""
  echo "HTML report: file://${PROJECT_ROOT}/htmlcov/index.html"
  exit 1
fi
