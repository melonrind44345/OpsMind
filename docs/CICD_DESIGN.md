# OpsMind CI/CD Pipeline Design

> **Version**: 0.1.0 | **Last Updated**: 2026-05-16
> **Target CI Platform**: GitHub Actions (可适配 GitLab CI/Jenkins)

---

## 目录

- [1. 流水线总览](#1-流水线总览)
- [2. 基础检查阶段](#2-基础检查阶段)
- [3. 自动化测试阶段](#3-自动化测试阶段)
- [4. 构建与发布阶段](#4-构建与发布阶段)
- [5. 完整 GitHub Actions 配置](#5-完整-github-actions-配置)
- [6. 本地 CI 验证](#6-本地-ci-验证)

---

## 1. 流水线总览

```
┌─────────────────────────────────────────────────────────────────┐
│                      Trigger: push / PR                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 1: 基础检查 (Parallel, ~30s)                              │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Ruff     │  │ Mypy     │  │ Bandit   │  │ Import Check  │  │
│  │ Format + │  │ Strict   │  │ Security │  │ (pip install) │  │
│  │ Lint     │  │ Type     │  │ Scan     │  │               │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │ (all pass)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 2: 自动化测试 (Parallel Matrix, ~2-3min)                  │
│                                                                 │
│  ┌────────────────────────────────────────┐                    │
│  │ Unit Tests (Python 3.11, 3.12)         │                    │
│  │  ├─ test_schemas.py                    │                    │
│  │  ├─ test_adapter.py                    │                    │
│  │  ├─ test_engine.py                     │                    │
│  │  └─ test_evaluators.py                 │                    │
│  ├────────────────────────────────────────┤                    │
│  │ Integration Tests (Python 3.11)        │                    │
│  │  └─ test_pipeline.py                   │                    │
│  ├────────────────────────────────────────┤                    │
│  │ Coverage Report                        │                    │
│  │  └─ pytest-cov (threshold: 80%)        │                    │
│  └────────────────────────────────────────┘                    │
└────────────────────────────┬────────────────────────────────────┘
                             │ (all pass)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 3: 构建与发布 (~2min)                                     │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐                   │
│  │ Build Package    │  │ Publish          │                   │
│  │  python -m build │─►│  ├─ PyPI (tag)   │                   │
│  │  (wheel + sdist) │  │  └─ GitHub Rel.  │                   │
│  └──────────────────┘  └──────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 基础检查阶段

### 2.1 代码格式与 Lint（Ruff）

**配置** (`pyproject.toml:79-85`)：

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM"]
```

**CI 步骤**：

```yaml
- name: Ruff - Lint & Format Check
  run: |
    pip install ruff
    ruff check src/opsmind/ tests/
    ruff format --check src/opsmind/ tests/
```

**本地运行**：

```bash
# 检查 lint
ruff check src/opsmind/ tests/

# 自动修复
ruff check --fix src/opsmind/

# 检查格式
ruff format --check src/opsmind/

# 自动格式化
ruff format src/opsmind/
```

### 2.2 类型检查（Mypy）

**配置** (`pyproject.toml:87-92`)：

```toml
[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
disallow_untyped_defs = true
disallow_any_unimported = false
warn_unused_ignores = true
```

**CI 步骤**：

```yaml
- name: Mypy - Strict Type Check
  run: |
    pip install mypy
    mypy src/opsmind/
```

**本地运行**：

```bash
mypy src/opsmind/
```

### 2.3 安全检查（Bandit）

```yaml
- name: Bandit - Security Scan
  run: |
    pip install bandit
    bandit -r src/opsmind/ -ll --skip B101
    # B101: assert 在测试外使用（开发阶段允许）
```

**常见安全规则**：

| 规则 ID | 描述 | 处理 |
|---------|------|------|
| B101 | `assert` 在非测试代码中使用 | skip（开发阶段） |
| B104 | 绑定到所有接口 (0.0.0.0) | 审查 |
| B602 | `subprocess.run` 使用 shell=True | 禁止 |
| B301 | `pickle` 反序列化 | 审查 |

### 2.4 导入完整性检查

```yaml
- name: Import Verification
  run: |
    pip install -e .
    python -c "import opsmind; print('Import OK')"
    python -c "from opsmind.core.engine import OpsMindEngine; print('Engine OK')"
    python -c "from opsmind.schemas.discovery import DiscoveryResult; print('Schemas OK')"
```

---

## 3. 自动化测试阶段

### 3.1 测试矩阵策略

```yaml
test:
  strategy:
    matrix:
      python-version: ["3.11", "3.12"]
      test-type: [unit, integration]
    fail-fast: false  # 不因一个版本失败而取消其他测试
```

### 3.2 单元测试

```yaml
- name: Unit Tests
  run: |
    pip install -e ".[dev]"
    pytest tests/unit/ -v --tb=short \
      --junitxml=junit-unit.xml \
      --cov=opsmind \
      --cov-report=xml:coverage-unit.xml \
      --cov-report=term
```

**测试清单**（映射到源代码）：

| 测试文件 | 覆盖的源代码 | 关键测试点 |
|---------|-------------|----------|
| `tests/unit/test_schemas.py` | `schemas/discovery.py`, `schemas/assessment.py`, `schemas/report.py` | 模型验证、字段约束、枚举值 |
| `tests/unit/test_adapter.py` | `discovery/adapters/ansible_adapter.py` | 事实映射、类型转换、空数据处理 |
| `tests/unit/test_engine.py` | `core/engine.py`, `core/events.py` | 引擎选择、方法解析、事件总线 |
| `tests/unit/test_evaluators.py` | `assessment/evaluators/feasibility.py`, `complexity.py`, `security.py` | 评分范围、维度完整性、策略生成 |

### 3.3 集成测试

```yaml
- name: Integration Tests
  run: |
    pip install -e ".[dev]"
    pytest tests/integration/ -v --tb=short \
      --junitxml=junit-integration.xml \
      --cov=opsmind \
      --cov-append \
      --cov-report=xml:coverage-integration.xml \
      --cov-report=term
```

**集成测试验证的端到端流程** (`tests/integration/test_pipeline.py`)：

| 测试方法 | 验证内容 |
|---------|---------|
| `test_discover_to_assess_pipeline` | 发现 → 评估数据流完整 |
| `test_markdown_report_generation` | MD 报告产出文件存在且可读 |
| `test_json_report_generation` | JSON 报告结构完整 |
| `test_docker_artifacts_generation` | Dockerfile + compose 文件生成 |
| `test_full_pipeline_with_remediation` | 全流水线（含产物） |
| `test_pipeline_events` | 事件总线正确发送所有阶段事件 |

### 3.4 覆盖率检查

```yaml
- name: Coverage Report & Threshold Check
  run: |
    pip install coverage
    coverage combine coverage-*.xml 2>/dev/null || true
    coverage report --fail-under=80
    coverage html -d htmlcov

- name: Upload Coverage Artifact
  uses: actions/upload-artifact@v4
  with:
    name: coverage-report
    path: htmlcov/
```

**覆盖率要求** (`pyproject.toml:66-77`)：

```toml
[tool.coverage.run]
source = ["opsmind"]
branch = true

[tool.coverage.report]
fail_under = 80
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "pass",
]
```

---

## 4. 构建与发布阶段

### 4.1 包构建

```yaml
- name: Build Package
  run: |
    pip install build
    python -m build
    # 产出: dist/opsmind-0.1.0-py3-none-any.whl
    #       dist/opsmind-0.1.0.tar.gz

- name: Verify Package
  run: |
    pip install twine
    twine check dist/*
```

**构建配置** (`pyproject.toml:1-3`)：

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"
```

**入口点** (`pyproject.toml:43-44`)：

```toml
[project.scripts]
opsmind = "opsmind.cli.main:app"
```

### 4.2 发布策略

**版本号规则**：遵循 SemVer (`MAJOR.MINOR.PATCH`)

| 分支 | 触发条件 | 发布目标 | 版本标签 |
|------|---------|---------|---------|
| `main` | 推送 tag `v*` | PyPI (正式版) | `0.1.0` |
| `main` | 推送到 main | TestPyPI (预发布) | `0.1.0.dev{N}` |
| PR | 创建/更新 PR | 不发布 | — |

**PyPI 发布**：

```yaml
- name: Publish to PyPI
  if: startsWith(github.ref, 'refs/tags/v')
  env:
    TWINE_USERNAME: ${{ secrets.PYPI_USERNAME }}
    TWINE_PASSWORD: ${{ secrets.PYPI_PASSWORD }}
  run: |
    pip install twine
    twine upload dist/*
```

**GitHub Release**：

```yaml
- name: Create GitHub Release
  if: startsWith(github.ref, 'refs/tags/v')
  uses: softprops/action-gh-release@v2
  with:
    files: dist/*
    generate_release_notes: true
```

### 4.3 Docker 镜像（可选）

```yaml
- name: Build Docker Image
  if: startsWith(github.ref, 'refs/tags/v')
  run: |
    docker build -t opsmind:${{ github.ref_name }} .
    docker tag opsmind:${{ github.ref_name }} ghcr.io/opsmind/opsmind:latest

- name: Push Docker Image
  run: |
    echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
    docker push ghcr.io/opsmind/opsmind:latest
    docker push ghcr.io/opsmind/opsmind:${{ github.ref_name }}
```

---

## 5. 完整 GitHub Actions 配置

```yaml
# .github/workflows/ci.yml
name: OpsMind CI/CD

on:
  push:
    branches: [main, develop]
    tags: ["v*"]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  # =========================================================================
  # Stage 1: 基础检查
  # =========================================================================
  lint-and-type:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install Dependencies
        run: pip install ruff mypy bandit

      - name: Ruff Check
        run: ruff check src/opsmind/ tests/

      - name: Ruff Format
        run: ruff format --check src/opsmind/ tests/

      - name: Mypy Type Check
        run: |
          pip install -e .
          mypy src/opsmind/

      - name: Bandit Security Scan
        run: bandit -r src/opsmind/ -ll --skip B101

      - name: Import Check
        run: python -c "from opsmind.core.engine import OpsMindEngine; from opsmind.schemas.discovery import DiscoveryResult; print('All imports OK')"

  # =========================================================================
  # Stage 2: 自动化测试
  # =========================================================================
  test:
    name: Test (Python ${{ matrix.python-version }}, ${{ matrix.test-type }})
    needs: lint-and-type
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
        test-type: [unit, integration]
      fail-fast: false

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"

      - name: Install Dependencies
        run: |
          pip install -e ".[dev]"
          pip install pytest pytest-cov pytest-mock

      - name: Run ${{ matrix.test-type }} Tests
        run: |
          if [ "${{ matrix.test-type }}" = "unit" ]; then
            pytest tests/unit/ -v --tb=short \
              --junitxml=junit-${{ matrix.test-type }}-py${{ matrix.python-version }}.xml \
              --cov=opsmind \
              --cov-report=xml:coverage-${{ matrix.test-type }}-py${{ matrix.python-version }}.xml \
              --cov-report=term
          else
            pytest tests/integration/ -v --tb=short \
              --junitxml=junit-${{ matrix.test-type }}-py${{ matrix.python-version }}.xml \
              --cov=opsmind \
              --cov-report=xml:coverage-${{ matrix.test-type }}-py${{ matrix.python-version }}.xml \
              --cov-report=term
          fi

      - name: Upload Test Results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results-${{ matrix.test-type }}-py${{ matrix.python-version }}
          path: |
            junit-*.xml
            coverage-*.xml

  # =========================================================================
  # 覆盖率聚合（在所有测试完成后运行）
  # =========================================================================
  coverage:
    name: Coverage Report
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Download Coverage Data
        uses: actions/download-artifact@v4
        with:
          pattern: test-results-*
          merge-multiple: true

      - name: Install Coverage
        run: pip install coverage

      - name: Generate Coverage Report
        run: |
          coverage combine coverage-*.xml 2>/dev/null || \
            coverage combine coverage-unit-py3.11.xml coverage-integration-py3.11.xml
          coverage report --fail-under=80
          coverage html -d htmlcov

      - name: Upload Coverage HTML
        uses: actions/upload-artifact@v4
        with:
          name: coverage-html
          path: htmlcov/

  # =========================================================================
  # Stage 3: 构建 & 发布
  # =========================================================================
  build-and-publish:
    name: Build & Publish
    needs: coverage
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Build Package
        run: |
          pip install build twine
          python -m build
          twine check dist/*

      - name: Publish to TestPyPI (main branch)
        if: github.ref == 'refs/heads/main' && !startsWith(github.ref, 'refs/tags/')
        env:
          TWINE_USERNAME: ${{ secrets.TESTPYPI_USERNAME }}
          TWINE_PASSWORD: ${{ secrets.TESTPYPI_PASSWORD }}
        run: |
          twine upload --repository testpypi dist/*

      - name: Publish to PyPI (tag)
        if: startsWith(github.ref, 'refs/tags/v')
        env:
          TWINE_USERNAME: ${{ secrets.PYPI_USERNAME }}
          TWINE_PASSWORD: ${{ secrets.PYPI_PASSWORD }}
        run: |
          twine upload dist/*

      - name: Create GitHub Release
        if: startsWith(github.ref, 'refs/tags/v')
        uses: softprops/action-gh-release@v2
        with:
          files: dist/*
          generate_release_notes: true

      - name: Upload Build Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
```

---

## 6. 本地 CI 验证

### 6.1 安装 CI 工具

```bash
pip install ruff mypy bandit pytest pytest-cov coverage build twine
```

### 6.2 本地一键验证脚本

创建 `scripts/ci-check.sh`：

```bash
#!/bin/bash
# OpsMind CI verification script — 模拟 CI 流水线的所有阶段
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }

echo "=== OpsMind CI Verification ==="
echo ""

# Stage 1: 基础检查
echo "--- Stage 1: Lint & Type Check ---"

echo "Running ruff..."
ruff check src/opsmind/ tests/ && pass "Ruff lint" || fail "Ruff lint"

echo "Running ruff format..."
ruff format --check src/opsmind/ tests/ && pass "Ruff format" || fail "Ruff format"

echo "Running mypy..."
mypy src/opsmind/ && pass "Mypy" || fail "Mypy"

echo "Running bandit..."
bandit -r src/opsmind/ -ll --skip B101 && pass "Bandit" || fail "Bandit"

echo ""
echo "--- Stage 2: Tests ---"

echo "Running unit tests..."
pytest tests/unit/ -v --tb=short --cov=opsmind --cov-report=term && pass "Unit tests" || fail "Unit tests"

echo "Running integration tests..."
pytest tests/integration/ -v --tb=short --cov=opsmind --cov-append --cov-report=term && pass "Integration tests" || fail "Integration tests"

echo "Checking coverage..."
coverage report --fail-under=80 && pass "Coverage >= 80%" || fail "Coverage < 80%"

echo ""
echo "--- Stage 3: Build ---"

echo "Building package..."
python -m build && pass "Build" || fail "Build"

echo "Checking package..."
twine check dist/* && pass "Twine check" || fail "Twine check"

echo ""
echo -e "${GREEN}=== All CI checks passed! ===${NC}"
```

### 6.3 使用方式

```bash
# 赋予执行权限
chmod +x scripts/ci-check.sh

# 运行完整检查
./scripts/ci-check.sh

# 或逐阶段运行
pytest tests/ -v --cov=opsmind
```

### 6.4 Pre-commit Hook

创建 `.git/hooks/pre-commit`（在 `.pre-commit-config.yaml` 不存在的情况下）：

```bash
#!/bin/bash
# 快速预提交检查——只运行 lint，不运行完整测试

echo "Running pre-commit checks..."

# Ruff lint + format（只检查修改的文件）
ruff check src/opsmind/ tests/ || exit 1

# 快速导入验证
python -c "from opsmind.core.engine import OpsMindEngine" || exit 1

echo "Pre-commit checks passed."
```

---

## 附录 A：配置与密钥管理

CI 所需的密钥配置：

| Secret | 用途 | 必需 |
|--------|------|------|
| `PYPI_USERNAME` | PyPI 发布用户名 | 仅 tag 发布时 |
| `PYPI_PASSWORD` | PyPI API token | 仅 tag 发布时 |
| `TESTPYPI_USERNAME` | TestPyPI 用户名 | 推荐 |
| `TESTPYPI_PASSWORD` | TestPyPI API token | 推荐 |
| `GITHUB_TOKEN` | GitHub Release / Docker 发布 | 自动注入 |

## 附录 B：状态徽章

```markdown
[![CI](https://github.com/opsmind/opsmind/actions/workflows/ci.yml/badge.svg)](https://github.com/opsmind/opsmind/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/opsmind/opsmind/branch/main/graph/badge.svg)](https://codecov.io/gh/opsmind/opsmind)
```

## 附录 C：CI 执行时间估算

| Stage | Job | 预估时间 |
|-------|-----|---------|
| Lint & Type | Ruff + Mypy + Bandit | ~30s |
| Test | Unit (3.11) | ~30s |
| Test | Unit (3.12) | ~30s |
| Test | Integration (3.11) | ~45s |
| Test | Integration (3.12) | ~45s |
| Coverage | 聚合 + 报告 | ~15s |
| Build | 构建 + 验证 | ~20s |
| Publish | PyPI 上传 | ~30s |
| **总计** | | **~4min** |
