# OpsMind User Manual

> **Version**: 0.1.0 | **适用于**: DevOps 工程师、架构师、系统管理员

---

## 目录

- [1. 新手快速开始（5分钟）](#1-新手快速开始5分钟)
- [2. 常用场景](#2-常用场景)
  - [场景A：本地系统评估](#场景a本地系统评估)
  - [场景B：远程服务器发现](#场景b远程服务器发现)
  - [场景C：批量主机评估](#场景c批量主机评估)
  - [场景D：生成容器化产物](#场景d生成容器化产物)
  - [场景E：报告对比](#场景e报告对比)
- [3. 命令参考](#3-命令参考)
- [4. 故障排除指南](#4-故障排除指南)

---

## 1. 新手快速开始（5分钟）

### 第一步：安装

```bash
# 克隆并安装
git clone https://github.com/opsmind/opsmind.git
cd opsmind
pip install -e .

# 验证安装
opsmind --version
# 输出: OpsMind v0.1.0 - Ansible-Driven Modernization Platform

# 检查环境依赖
opsmind validate
```

**预期输出**：
```
OpsMind System Validation

✓ Python 3.11.x
✓ Ansible: ansible [core 2.15.x]
✓ Docker: Docker version 24.x.x
✓ psutil: installed

All checks passed!
```

### 第二步：运行 Demo（无需任何外部依赖）

```bash
# 交互式演示，展示全部 4 个阶段的能力
opsmind demo
```

这将自动执行：
1. **系统发现** — 模拟一个 CentOS 6 遗留系统
2. **智能评估** — 多维度可行性评分
3. **报告生成** — 同时生成 MD/JSON/HTML 三种报告
4. **产物生成** — Dockerfile、docker-compose.yml、迁移计划

### 第三步：评估你自己的系统

```bash
# 一键流水线：发现 → 评估 → 报告
opsmind pipeline localhost --report-format html

# 查看生成的报告
open opsmind_report.html
```

**就这么简单！** 你已经完成了第一次真实的系统容器化评估。

---

## 2. 常用场景

### 场景A：本地系统评估

**目标**：评估当前开发机器是否适合容器化。

```bash
# 方式1: 一键流水线（推荐）
opsmind pipeline localhost -f markdown

# 方式2: 分步执行（更多控制）
opsmind discover localhost --method native    # 使用本地检测
opsmind assess -f json -d detailed            # 评估并生成 JSON 报告

# 方式3: 使用 Ansible 获取最丰富的数据
opsmind discover localhost --method ansible
opsmind assess -f html
```

**关键参数说明**：
- `--method native`: 使用 psutil 检测，无需安装 Ansible
- `--method ansible`: 使用 Ansible setup 模块，数据最全面
- `-f html`: 生成带图表的自包含 HTML 报告
- `-d detailed`: 详细级别报告（可选：executive, summary, detailed, raw）

### 场景B：远程服务器发现

**目标**：评估一台生产服务器的容器化可行性。

```bash
# 前置条件：确保 SSH 免密登录已配置
ssh -i ~/.ssh/id_rsa ubuntu@192.168.1.100 "uname -a"

# 执行远程发现 + 评估
opsmind pipeline 192.168.1.100 \
    --method ansible \
    --ssh-user ubuntu \
    --ssh-key ~/.ssh/id_rsa \
    --report-format html \
    --remediation
```

**输出产物**：
```
opsmind_report.html                  # 评估报告
opsmind_artifacts/docker/            # Docker 配置
  └── <hostname>/
      ├── Dockerfile
      ├── docker-compose.yml
      ├── .dockerignore
      └── build.sh
opsmind_artifacts/plans/             # 迁移计划
  ├── <hostname>_migration_plan.md
  └── 00_migration_overview.md
```

**安全提示**：
- 使用 SSH Key 而非密码认证
- 首次连接前确认主机指纹
- 生产环境建议先用 `opsmind validate` 检查连通性

### 场景C：批量主机评估

**目标**：一次评估多台服务器。

```bash
# 方式1: 逗号分隔主机列表
opsmind pipeline "192.168.1.100,192.168.1.101,192.168.1.102" \
    --method ansible \
    --ssh-user ubuntu \
    --report-format json

# 方式2: 使用 Ansible inventory 文件
cat > inventory.yml << 'EOF'
---
all:
  hosts:
    web-01:
      ansible_host: 192.168.1.10
    web-02:
      ansible_host: 192.168.1.11
    db-01:
      ansible_host: 192.168.1.20
EOF

opsmind pipeline all --method ansible --inventory inventory.yml -f html
```

**批量评估输出示例**：
```
╭─────────── Pipeline Summary ───────────╮
│ Discovery:  3 hosts successful         │
│ Assessment: 3 hosts evaluated          │
│ Report:     opsmind_report.html        │
│ Total Time: 15.3s                      │
╰────────────────────────────────────────╯

Host Assessment Scores:
┌─────────┬───────┬────────────┬──────┬──────────┐
│ Host    │ Score │ Complexity │ Risk │ Strategy  │
├─────────┼───────┼────────────┼──────┼──────────┤
│ web-01  │ 32.5  │ complex    │ high │ refactor │
│ web-02  │ 45.0  │ complex    │ high │ refactor │
│ db-01   │ 78.0  │ moderate   │ low  │ rehost   │
└─────────┴───────┴────────────┴──────┴──────────┘
```

### 场景D：生成容器化产物

**目标**：从评估结果生成可执行的 Docker 配置和迁移计划。

```bash
# 完整流水线（含产物生成）
opsmind pipeline localhost -r

# 或者分步执行
opsmind discover localhost
opsmind assess
opsmind generate docker                # 生成 Docker 配置
opsmind generate migration-plan        # 生成迁移计划
```

**生成的 Dockerfile 示例**（`opsmind_artifacts/docker/<host>/Dockerfile`）：

```dockerfile
# OpsMind Generated Dockerfile
# Generated: 2026-05-16 10:30:00
# Host: legacy-app-01
# Strategy: refactor
# Feasibility Score: 32.5/100

FROM ubuntu:22.04

LABEL opsmind.host="legacy-app-01" \
      opsmind.generated="2026-05-16" \
      opsmind.version="0.1.0" \
      description="Containerized legacy-app-01 - complex migration"

RUN apt-get update && apt-get install -y \
    nginx mysql-server cron curl wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

CMD ["bash"]
```

**优化选项**（`--optimize` 参数）：

```bash
# 生成体积优化版 Dockerfile（多阶段构建）
opsmind generate docker --optimize size

# 查看生成的产物
ls opsmind_artifacts/docker/<hostname>/
# Dockerfile  docker-compose.yml  .dockerignore  build.sh
```

### 场景E：报告对比

**目标**：对比两次评估结果，追踪改进进度。

```bash
# 第一次评估
opsmind pipeline localhost -f json -o baseline_report.json

# ... 进行系统优化（升级 OS、安装 Docker 等） ...

# 第二次评估
opsmind pipeline localhost -f json -o current_report.json

# 查看当前报告
opsmind report show

# 对比两次结果
opsmind report compare --baseline baseline_report.json
```

**对比输出示例**：
```
╭─────────── Comparison ───────────╮
│ Baseline Score: 45.0             │
│ Current Score:  72.5             │
│ Delta:          +27.5            │
╰──────────────────────────────────╯
```

---

## 3. 命令参考

### `opsmind discover` — 系统发现

```bash
opsmind discover <target> [OPTIONS]
```

| 选项 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--method` | `-m` | 发现方法: ansible, native, mock, auto | `auto` |
| `--inventory` | `-i` | Ansible inventory 文件路径 | 自动生成 |
| `--ssh-user` | `-u` | SSH 用户名 | — |
| `--ssh-key` | `-k` | SSH 私钥路径 | — |
| `--output` | `-o` | 输出 JSON 文件路径 | — |

### `opsmind assess` — 可行性评估

```bash
opsmind assess [OPTIONS]
```

| 选项 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--report-format` | `-f` | 报告格式: markdown, json, html | `markdown` |
| `--detail-level` | `-d` | 详细级别: executive, summary, detailed, raw | `detailed` |
| `--output` | `-o` | 报告输出路径 | `opsmind_report.{format}` |

### `opsmind generate` — 生成产物

```bash
opsmind generate <artifact> [OPTIONS]
```

`artifact`: `docker` 或 `migration-plan`

| 选项 | 简写 | 说明 |
|------|------|------|
| `--optimize` | `-o` | 优化目标: `performance`, `size`, `cost` |
| `--output-dir` | `-d` | 输出目录 |

### `opsmind report` — 报告操作

```bash
opsmind report <action> [OPTIONS]
```

`action`: `show`, `export`, `compare`

| 选项 | 简写 | 说明 |
|------|------|------|
| `--format` | `-f` | 导出格式 |
| `--output` | `-o` | 输出路径 |
| `--baseline` | `-b` | 对比基线文件路径（compare 操作必选） |

### `opsmind pipeline` — 完整流水线

```bash
opsmind pipeline <target> [OPTIONS]
```

| 选项 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--method` | `-m` | 发现方法 | `auto` |
| `--report-format` | `-f` | 报告格式 | `markdown` |
| `--output-dir` | `-o` | 输出目录 | 当前目录 |
| `--remediation` | `-r` | 同时生成容器化产物 | `False` |
| `--optimize` | — | 产物优化目标 | — |

### `opsmind validate` — 环境验证

```bash
opsmind validate [--check] [--fix]
```

### `opsmind demo` — 交互式演示

```bash
opsmind demo
```

---

## 4. 故障排除指南

### 问题 1: `opsmind: command not found`

**原因**：OpsMind 未正确安装。

**解决**：
```bash
# 确认虚拟环境已激活
which python3
# 应该在 .venv/bin/python3

# 重新安装
pip install -e .
opsmind --version
```

### 问题 2: `Ansible not available`

**现象**：
```
○ Ansible: not installed (fallback available)
```
或者：
```
AnsibleNotAvailableError: Ansible is not available on this system
```

**原因**：Ansible 未安装或不在 PATH 中。

**解决方案（按优先级）**：

```bash
# 方案A: 安装 Ansible（推荐，数据最全）
pip install ansible-core
# 验证
ansible --version

# 方案B: 使用本地检测（无需 Ansible）
opsmind discover localhost --method native

# 方案C: 使用模拟数据（演示/测试）
opsmind discover localhost --method mock
```

### 问题 3: SSH 连接失败

**现象**：
```
SSHConnectionError: SSH connection failed to 192.168.1.100
```

**排查步骤**：

```bash
# 1. 测试 SSH 连通性
ssh -i ~/.ssh/id_rsa ubuntu@192.168.1.100 "uname -a"

# 2. 检查 SSH Key 权限
chmod 600 ~/.ssh/id_rsa

# 3. 验证目标主机 Python 可用
ssh ubuntu@192.168.1.100 "which python3 || which python"

# 4. 使用 verbose 模式调试
opsmind discover 192.168.1.100 -m ansible -u ubuntu -k ~/.ssh/id_rsa
```

### 问题 4: 评估分数异常低或高

**原因**：Mock 数据或数据采集不完整。

**检查数据来源**：
```bash
# 查看数据置信度
opsmind discover localhost -m ansible -o discovery.json
cat discovery.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('_metadata',{}))"

# 预期置信度：
# - ansible 方法 → HIGH 置信度
# - native 方法 → HIGH 置信度
# - mock 方法   → LOW 置信度 + "Mock data" 警告
```

### 问题 5: Docker 产物生成失败

**现象**：
```
○ Docker: not installed
```

**解决**：
```bash
# Docker 产物生成不依赖 Docker daemon
# 只需要文件写入权限即可
opsmind generate docker --output-dir ./my-artifacts

# 验证文件权限
ls -la ./my-artifacts/docker/<hostname>/
```

### 问题 6: 内存不足或处理缓慢

**优化策略**：

```bash
# 大数量主机：分批处理
opsmind pipeline "192.168.1.100,192.168.1.101" -f json
opsmind pipeline "192.168.1.102,192.168.1.103" -f json

# 使用 Ansible inventory 分组并行
# 编辑 ansible.cfg:
# [defaults]
# forks = 20           # 增加并发数
# pipelining = True    # 减少 SSH 往返

# 只生成需要的格式
opsmind assess -f json    # 比 HTML 更快
```

### 问题 7: 报告内容不完整

**提升详细级别**：

```bash
# 四种详细级别
opsmind assess -d executive    # 仅执行摘要（最简）
opsmind assess -d summary      # 关键发现
opsmind assess -d detailed     # 完整分析（默认）
opsmind assess -d raw          # 所有原始数据（最全）
```

### 诊断命令速查

```bash
# 环境诊断
opsmind validate

# 查看版本
opsmind --version

# Ansible 连接性测试
ansible all -i <inventory> -m ping

# 查看日志（JSON 格式）
cat /tmp/opsmind/opsmind.log | python3 -m json.tool | tail -20

# 以 verbose 模式运行
python3 -c "
from opsmind.core.engine import OpsMindEngine
engine = OpsMindEngine()
result = engine.discover('localhost', method='mock')
for h, d in result.hosts.items():
    print(f'{h}: {d.hardware.cpu.model}, {d.software.os_name} {d.software.os_version}')
"
```
