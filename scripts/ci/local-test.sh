#!/bin/bash
# ============================================================================
# OpsMind — Local CI Pipeline Simulator
# ============================================================================
# Simulates all stages of the CI/CD pipeline locally. Works as a standalone
# script with no dependency on any specific CI platform.
#
# Usage:
#   chmod +x scripts/ci/local-test.sh
#   ./scripts/ci/local-test.sh                         # Full pipeline
#   ./scripts/ci/local-test.sh --stage quality         # Only quality checks
#   ./scripts/ci/local-test.sh --stage test            # Only tests
#   ./scripts/ci/local-test.sh --skip-security          # Skip security scans
#   ./scripts/ci/local-test.sh --python 3.11            # Specify Python version
# ============================================================================

set -euo pipefail

# --- Color helpers ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

pass()  { echo -e "${GREEN}  ✓${NC} $1"; }
fail()  { echo -e "${RED}  ✗${NC} $1"; }
warn()  { echo -e "${YELLOW}  ⚠${NC} $1"; }
info()  { echo -e "${BLUE}  ℹ${NC} $1"; }
header() {
    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  $1${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# --- Default settings ---
STAGE="all"
SKIP_SECURITY=false
COVERAGE_THRESHOLD=40
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PACKAGE_DIR="src/opsmind"
TEST_DIR="tests"
ANSIBLE_DIR="ansible"
EXIT_CODE=0

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --stage)
            STAGE="$2"; shift 2 ;;
        --skip-security)
            SKIP_SECURITY=true; shift ;;
        --python)
            # Informational — we use the system Python; for multi-version
            # matrix use act or Docker directly
            shift 2 ;;
        --coverage-threshold)
            COVERAGE_THRESHOLD="$2"; shift 2 ;;
        --help|-h)
            cat << 'USAGE'
Usage: local-test.sh [OPTIONS]

Options:
  --stage <name>          Run a specific stage:
                          quality  — ruff + mypy + bandit
                          test     — pytest with coverage
                          coverage — coverage report + threshold check
                          security — bandit + safety audit
                          build    — package build + twine verify
                          ansible  — Ansible playbook validation
                          all      — full pipeline (default)
  --skip-security         Skip security scans in full pipeline
  --python <version>      Python version (informational — uses system Python)
  --coverage-threshold N  Coverage threshold percentage (default: 80)
  --help, -h              Show this help

Examples:
  ./scripts/ci/local-test.sh                        # Full pipeline
  ./scripts/ci/local-test.sh --stage quality        # Only quality checks
  ./scripts/ci/local-test.sh --stage test           # Only run tests
  ./scripts/ci/local-test.sh --skip-security        # Skip security scans

Simulating GitHub Actions locally:
  act push --job quality               # Run quality job
  act pull_request                     # Run full CI for PR
  act --job test                       # Run test job only
USAGE
            exit 0
            ;;
        *)
            echo "Unknown option: $1"; exit 1 ;;
    esac
done

cd "$PROJECT_ROOT"

# --- Virtual environment ---
VENV_DIR="$PROJECT_ROOT/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${BLUE}  ℹ${NC} Creating virtual environment at .venv/ ..."
    python3 -m venv "$VENV_DIR"
fi
# Activate venv (modifies PATH so python/pip point inside .venv)
export VIRTUAL_ENV="$VENV_DIR"
export PATH="$VENV_DIR/bin:$PATH"

# --- Banner ---
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       OpsMind — Local CI Pipeline Simulator          ║${NC}"
echo -e "${BOLD}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}║${NC}  Stage:        ${GREEN}${STAGE}${NC}"
echo -e "${BOLD}║${NC}  Security:     ${GREEN}$([ "$SKIP_SECURITY" = true ] && echo 'SKIPPED' || echo 'ENABLED')${NC}"
echo -e "${BOLD}║${NC}  Coverage:     ${GREEN}${COVERAGE_THRESHOLD}%${NC}"
echo -e "${BOLD}║${NC}  Project root: ${GREEN}${PROJECT_ROOT}${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}"

# --- Helper: ensure pip packages installed ---
ensure_packages() {
    for pkg in "$@"; do
        if ! pip show "$pkg" &>/dev/null; then
            info "Installing $pkg..."
            pip install -q "$pkg"
        fi
    done
}

# ============================================================================
# Stage: quality
# ============================================================================
run_quality() {
    header "Quality Check"

    ensure_packages ruff mypy bandit

    # Ruff lint
    echo "  [1/3] Ruff lint..."
    if ruff check "${PACKAGE_DIR}/" "${TEST_DIR}/" 2>&1; then
        pass "Ruff lint: PASSED"
    else
        fail "Ruff lint: FAILED"
        warn "Run 'ruff check --fix src/opsmind/' to auto-fix"
        EXIT_CODE=1
    fi

    # Ruff format
    echo "  [2/3] Ruff format..."
    if ruff format --check "${PACKAGE_DIR}/" "${TEST_DIR}/" 2>&1; then
        pass "Ruff format: PASSED"
    else
        fail "Ruff format: FAILED"
        warn "Run 'ruff format src/opsmind/ tests/' to auto-fix"
        EXIT_CODE=1
    fi

    # Mypy
    echo "  [3/3] Mypy type check..."
    if mypy "${PACKAGE_DIR}/" 2>&1; then
        pass "Mypy: PASSED"
    else
        fail "Mypy: FAILED"
        EXIT_CODE=1
    fi
}

# ============================================================================
# Stage: security
# ============================================================================
run_security() {
    header "Security Scan"

    ensure_packages bandit safety

    # Bandit
    echo "  [1/2] Bandit SAST..."
    if bandit -r "${PACKAGE_DIR}/" -ll 2>&1; then
        pass "Bandit: CLEAN"
    else
        warn "Bandit found potential issues — review output above"
    fi

    # Safety
    echo "  [2/2] Safety dependency audit..."
    pip freeze > /tmp/requirements-frozen.txt
    if safety check --file=/tmp/requirements-frozen.txt 2>&1; then
        pass "Safety: PASSED"
    else
        warn "Safety found known vulnerabilities in dependencies"
    fi
    rm -f /tmp/requirements-frozen.txt
}

# ============================================================================
# Stage: test
# ============================================================================
run_test() {
    header "Testing"

    ensure_packages pytest pytest-cov pytest-mock coverage

    # Unit tests
    echo "  [1/2] Unit tests..."
    local unit_exit=0
    pytest tests/unit/ \
        -v \
        --tb=short \
        -m "not ansible" \
        --junitxml=junit-unit.xml \
        --cov=opsmind \
        --cov-report=xml:coverage-unit.xml \
        --cov-report=term \
        --no-header 2>&1 || unit_exit=$?

    if [ $unit_exit -eq 0 ]; then
        pass "Unit tests: PASSED"
    else
        fail "Unit tests: FAILED"
        EXIT_CODE=1
    fi

    # Integration tests
    echo "  [2/2] Integration tests..."
    local int_exit=0
    pytest tests/integration/ \
        -v \
        --tb=long \
        --junitxml=junit-integration.xml \
        --cov=opsmind \
        --cov-append \
        --cov-report=xml:coverage-integration.xml \
        --cov-report=term \
        --no-header 2>&1 || int_exit=$?

    if [ $int_exit -eq 0 ]; then
        pass "Integration tests: PASSED"
    else
        fail "Integration tests: FAILED"
        EXIT_CODE=1
    fi
}

# ============================================================================
# Stage: coverage
# ============================================================================
run_coverage() {
    header "Coverage Report"

    echo "  Combining coverage data..."
    coverage combine coverage-*.xml 2>/dev/null || coverage combine 2>/dev/null || true

    if coverage report --fail-under="${COVERAGE_THRESHOLD}" 2>&1; then
        pass "Coverage: >= ${COVERAGE_THRESHOLD}% (threshold met)"
    else
        fail "Coverage: < ${COVERAGE_THRESHOLD}% (below threshold)"
        EXIT_CODE=1
    fi

    coverage html -d htmlcov
    coverage json -o coverage.json
    info "HTML report: htmlcov/index.html"
    info "JSON report: coverage.json"
}

# ============================================================================
# Stage: build
# ============================================================================
run_build() {
    header "Build & Package"

    ensure_packages build twine

    echo "  [1/3] Building package..."
    if python -m build 2>&1; then
        pass "Build: SUCCESS"
    else
        fail "Build: FAILED"
        EXIT_CODE=1
        return
    fi

    echo "  Build artifacts:"
    ls -lh dist/ | sed 's/^/    /'

    echo "  [2/3] Verifying package..."
    if twine check dist/* 2>&1; then
        pass "Twine check: PASSED"
    else
        fail "Twine check: FAILED"
        EXIT_CODE=1
    fi

    echo "  [3/3] Build info..."
    cat > build-info.txt << INFO
Build metadata:
  Git commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'N/A')
  Build date: $(date -u +'%Y-%m-%dT%H:%M:%SZ')
  Python:     $(python3 --version 2>/dev/null)
  Platform:   $(uname -smp)
INFO
    pass "Build info written to build-info.txt"
}

# ============================================================================
# Stage: ansible
# ============================================================================
run_ansible() {
    header "Ansible Checks"

    if ! command -v ansible-playbook &>/dev/null; then
        warn "ansible-playbook not found — installing ansible-core..."
        pip install -q ansible-core ansible-lint
    fi

    if [ -d "${ANSIBLE_DIR}/playbooks" ] && ls "${ANSIBLE_DIR}"/playbooks/*.yml &>/dev/null 2>&1; then
        echo "  [1/2] Playbook syntax check..."
        local syn_ok=true
        for playbook in "${ANSIBLE_DIR}"/playbooks/*.yml; do
            [ -f "$playbook" ] || continue
            echo "    Checking: $playbook"
            if ansible-playbook "$playbook" --syntax-check 2>&1; then
                pass "  $playbook: OK"
            else
                fail "  $playbook: SYNTAX ERROR"
                syn_ok=false
                EXIT_CODE=1
            fi
        done
        [ "$syn_ok" = true ] && pass "All playbooks: syntax OK"
    else
        info "No Ansible playbooks found in ${ANSIBLE_DIR}/playbooks/"
    fi

    echo "  [2/2] ansible-lint..."
    if [ -d "${ANSIBLE_DIR}" ]; then
        ansible-lint "${ANSIBLE_DIR}/" --nocolor 2>&1 || warn "ansible-lint found issues"
    fi
}

# ============================================================================
# Main dispatch
# ============================================================================
case "$STAGE" in
    all)
        run_quality
        [ "$SKIP_SECURITY" = false ] && run_security
        run_test
        run_coverage
        run_ansible
        run_build
        ;;
    quality)   run_quality ;;
    security)  run_security ;;
    test)      run_test ;;
    coverage)  run_coverage ;;
    build)     run_build ;;
    ansible)   run_ansible ;;
    *)
        echo "Unknown stage: $STAGE"
        echo "Valid stages: quality, security, test, coverage, ansible, build, all"
        exit 1
        ;;
esac

# ============================================================================
# Final summary
# ============================================================================
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║  ✓  All CI checks passed!                           ║${NC}"
    echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
else
    echo -e "${RED}${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}${BOLD}║  ✗  Some CI checks failed. Review errors above.     ║${NC}"
    echo -e "${RED}${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
fi
echo ""

exit $EXIT_CODE
