# OpsMind CI/CD Guide

> **Version**: 0.2.0 | **Last Updated**: 2026-05-19
> **CI Platform**: GitHub Actions

---

## 目录

- [1. GitHub Actions CI](#1-github-actions-ci)
  - [1.1 工作流概览](#11-工作流概览)
  - [1.2 快速开始](#12-快速开始)
  - [1.3 本地测试](#13-本地测试)
  - [1.4 发布流程](#14-发布流程)
  - [1.5 版本管理](#15-版本管理)

---

# 1. GitHub Actions CI

## 1.1 工作流概览

OpsMind 使用 GitHub Actions 作为主要 CI/CD 平台，提供自动化代码质量检查、测试、安全扫描、包构建和发布。

### 工作流文件

| 工作流 | 文件 | 触发条件 | 用途 |
|--------|------|---------|------|
| **CI** | `.github/workflows/ci.yml` | push/PR to main, develop | 代码质量 + 测试 + 构建验证 |
| **Release** | `.github/workflows/release.yml` | tag `v*.*.*` | PyPI 发布 + Docker 推送 + GitHub Release |
| **Docker** | `.github/workflows/docker.yml` | push to main, PR (Dockerfile 变更) | Docker 镜像构建 + 安全扫描 |
| **Security** | `.github/workflows/security.yml` | 每周一 09:37 CST | 依赖漏洞 + SAST + 镜像扫描 |

### 流水线架构

```
Push / Pull Request
    │
    ▼
Quality (并行)
├── ruff-lint
├── ruff-format
├── mypy
└── bandit
    │
    ▼
Test Matrix (并行)
├── Python 3.11 (unit + integration)
└── Python 3.12 (unit + integration)
    │
    ▼
Coverage Report ← 合并覆盖率, 检查 80% 阈值
    │
    ▼
Build Check ← 构建 wheel/sdist + twine 验证
```

### Quality Gate 失败策略

| 检查项 | 工具 | 失败行为 |
|--------|------|---------|
| Lint | ruff check | 阻断, 提供 auto-fix 命令 |
| Format | ruff format --check | 阻断, 提供 auto-fix 命令 |
| Type Check | mypy | 阻断, 输出具体错误行 |
| SAST | bandit | 警示, 不阻断 |

## 1.2 快速开始

### 启用 GitHub Actions

GitHub Actions 在推送 `.github/workflows/` 目录后自动生效。无需额外配置。

### 查看 CI 状态

1. 推送代码或创建 PR
2. 在 GitHub 仓库页面的 **Actions** tab 查看运行状态
3. PR 页面底部会显示 CI 检查状态

### 手动触发

在 **Actions** tab 中选择对应 workflow，点击 **Run workflow** 按钮。

### CI Badge

```markdown
[![CI](https://github.com/melonrind44345/OpsMind/actions/workflows/ci.yml/badge.svg)](https://github.com/melonrind44345/OpsMind/actions/workflows/ci.yml)
```

## 1.3 本地测试

### 方案一：local-test.sh (快速)

```bash
# 赋予执行权限
chmod +x scripts/ci/local-test.sh

# 完整流水线
./scripts/ci/local-test.sh

# 仅质量检查
./scripts/ci/local-test.sh --stage quality

# 仅测试
./scripts/ci/local-test.sh --stage test

# 跳过安全扫描
./scripts/ci/local-test.sh --skip-security
```

### 方案二：act (完整 GitHub Actions 模拟)

```bash
# 安装 act
# macOS: brew install act
# Linux:
curl -fsSL https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# 运行 CI 工作流
act push --job quality
act pull_request

# 运行 release (dry-run)
act release --job build
```

### 方案三：Docker (环境隔离)

```bash
docker run --rm -v $(pwd):/workspace -w /workspace python:3.11-slim \
  bash -c "pip install -e . && pip install ruff mypy pytest && ruff check src/opsmind/ && pytest tests/ -v"
```

## 1.4 发布流程

### 创建 Release

1. 确保所有代码已合并到 `main` 分支且 CI 通过
2. 在本地创建 annotated tag:
   ```bash
   git tag -a v0.2.0 -m "Release v0.2.0"
   git push origin v0.2.0
   ```
3. GitHub Actions 自动执行:
   - 构建 Python 分发包 (wheel + sdist)
   - 发布到 PyPI (OIDC Trusted Publishing)
   - 构建 Docker 镜像并推送到 GHCR
   - 创建 GitHub Release 并附上 changelog

### PyPI 配置

本项目使用 **PyPI OIDC Trusted Publishing**，无需配置 API Token:
- GitHub Actions 通过 OIDC 自动获取短期令牌
- 首次使用需在 PyPI 项目设置中添加 Trusted Publisher
- Publisher: `https://github.com/melonrind44345/OpsMind`
- Workflow: `release.yml`
- Environment: `pypi`

### Docker 镜像

镜像发布到 GitHub Container Registry:
```
ghcr.io/melonrind44345/opsmind:latest
ghcr.io/melonrind44345/opsmind:v0.2.0
ghcr.io/melonrind44345/opsmind:sha-abc1234
```

拉取镜像:
```bash
docker pull ghcr.io/melonrind44345/opsmind:latest
docker run --rm ghcr.io/melonrind44345/opsmind:latest --version
```

## 1.5 版本管理

OpsMind 遵循 [Semantic Versioning](https://semver.org/) 并使用 Conventional Commits:

| 提交类型 | 版本变化 | 示例 |
|---------|---------|------|
| `feat:` | Minor (0.1.0 → 0.2.0) | `feat: add redis discovery engine` |
| `fix:` | Patch (0.1.0 → 0.1.1) | `fix: resolve SSH timeout on slow hosts` |
| `feat!:` / `fix!:` | Major (0.1.0 → 1.0.0) | `feat!: drop Python 3.9 support` |
| `chore:` / `docs:` / `style:` | 不变 | 仅 CI/文档/格式变更 |

版本号在 `pyproject.toml` 的 `[project] version` 字段手动管理，或通过 release-please 自动管理。

---

## 相关文档

- [Developer Guide](DEVELOPER_GUIDE.md) — CI/CD 开发流程
- [CI/CD Design](CICD_DESIGN.md) — 原始设计文档
