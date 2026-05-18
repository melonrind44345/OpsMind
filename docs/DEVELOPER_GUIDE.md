# OpsMind Developer Guide

> **Version**: 0.1.0 | **受众**: 希望扩展 OpsMind 的开发者

---

## 目录

- [1. 项目结构概览](#1-项目结构概览)
- [2. 如何添加新的发现器](#2-如何添加新的发现器)
- [3. 如何扩展评估规则](#3-如何扩展评估规则)
- [4. 如何添加新的报告格式](#4-如何添加新的报告格式)
- [5. 代码规范](#5-代码规范)
- [6. 测试要求](#6-测试要求)

---

## 1. 项目结构概览

```
src/opsmind/
├── cli/main.py                    # CLI 入口 — 添加新命令
├── core/
│   ├── engine.py                  # 工作流协调器 — 注册新引擎/评估器
│   ├── events.py                  # 事件总线（单例）
│   └── exceptions.py              # 异常层次结构
├── schemas/
│   ├── discovery.py               # 发现数据模型 (Pydantic v2)
│   ├── assessment.py              # 评估结果模型
│   └── report.py                  # 报告数据模型
├── discovery/
│   ├── engines/                   # 发现引擎实现
│   │   ├── base.py               # BaseDiscoveryEngine (ABC)
│   │   ├── ansible_engine.py     # Ansible SSH 发现
│   │   ├── native_engine.py      # 本地 psutil 发现
│   │   └── mock_engine.py        # 模拟数据引擎
│   ├── adapters/                  # 原始数据 → 统一模型
│   │   ├── base_adapter.py       # BaseAdapter (ABC)
│   │   └── ansible_adapter.py    # Ansible facts 适配器
│   └── collectors/                # 辅助数据采集器
├── assessment/evaluators/         # 评估器实现
├── reporting/generators/          # 报告生成器
├── remediation/generators/        # 产物生成器
└── utils/                         # 工具函数
```

---

## 2. 如何添加新的发现器

添加一个新的发现引擎需要实现 `BaseDiscoveryEngine` 接口并注册到引擎中。

### 2.1 接口定义

所有发现引擎必须实现 `src/opsmind/discovery/engines/base.py:9` 中的抽象基类：

```python
# src/opsmind/discovery/engines/base.py
from abc import ABC, abstractmethod
from typing import List
from opsmind.schemas.discovery import DiscoveryResult, DiscoveryMethod

class BaseDiscoveryEngine(ABC):
    @property
    @abstractmethod
    def method(self) -> DiscoveryMethod:
        """返回此引擎实现的发现方法枚举值。"""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """检查此引擎在当前系统上是否可用。"""
        ...

    @abstractmethod
    def discover_host(self, host: str) -> DiscoveryResult:
        """发现单个主机并返回结构化的 DiscoveryResult。"""
        ...

    @abstractmethod
    def discover_group(self, hosts: List[str], parallel: bool = True) -> DiscoveryResult:
        """发现多个主机，可选并行执行。"""
        ...
```

### 2.2 实现示例：添加 SaltStack 发现引擎

以下完整示例展示如何添加基于 SaltStack 的发现引擎：

**步骤 1：创建引擎文件** `src/opsmind/discovery/engines/salt_engine.py`

```python
"""SaltStack-powered discovery engine."""

import time
from typing import Any, Dict, List, Optional

from opsmind.discovery.engines.base import BaseDiscoveryEngine
from opsmind.schemas.discovery import (
    ConfidenceLevel,
    CPUInfo,
    DataSource,
    DiscoveryMethod,
    DiscoveryResult,
    DiskInfo,
    HardwareSpec,
    MemoryInfo,
    UnifiedDiscoveryModel,
)


class SaltDiscoveryEngine(BaseDiscoveryEngine):
    """通过 SaltStack 收集系统信息的发现引擎。"""

    def __init__(
        self,
        master_config: Optional[str] = None,
        timeout: int = 10,
    ) -> None:
        self.master_config = master_config
        self.timeout = timeout
        self._available: Optional[bool] = None

    @property
    def method(self) -> DiscoveryMethod:
        # 在 schemas/discovery.py 的 DiscoveryMethod 中添加 SALT = "salt"
        return DiscoveryMethod.SALT

    @property
    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        self._available = self._check_salt()
        return self._available

    def _check_salt(self) -> bool:
        """检查 salt 命令是否可用。"""
        import subprocess
        try:
            result = subprocess.run(
                ["salt", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def discover_host(self, host: str) -> DiscoveryResult:
        """通过 Salt grains 发现单个主机。"""
        import subprocess
        import json

        start_time = time.time()

        # 执行 salt grains.items
        result = subprocess.run(
            ["salt", host, "grains.items", "--out=json", f"--timeout={self.timeout}"],
            capture_output=True, text=True, timeout=self.timeout + 10,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Salt discovery failed for {host}: {result.stderr[:200]}")

        grains = json.loads(result.stdout).get(host, {})

        # 将 grains 转换为 UnifiedDiscoveryModel
        unified = self._grains_to_unified(grains, host)

        duration = (time.time() - start_time) * 1000
        unified.metadata = self._create_metadata(
            host=host,
            source="salt.grains",  # 需在 DataSource 枚举中注册
            duration_ms=duration,
        )
        unified.metadata.confidence = ConfidenceLevel.HIGH

        return DiscoveryResult(
            hosts={host: unified},
            total_hosts=1,
            successful_hosts=1,
            total_duration_ms=duration,
        )

    def discover_group(self, hosts: List[str], parallel: bool = True) -> DiscoveryResult:
        """发现多个 Salt minion。"""
        if not hosts:
            return DiscoveryResult()

        result = DiscoveryResult()
        # Salt 原生支持批量操作
        for host in hosts:
            try:
                host_result = self.discover_host(host)
                result.hosts.update(host_result.hosts)
                result.successful_hosts += 1
            except Exception as exc:
                result.failed_hosts += 1
                result.errors[host] = [str(exc)]

        result.total_hosts = len(hosts)
        return result

    def _grains_to_unified(self, grains: Dict[str, Any], host: str) -> UnifiedDiscoveryModel:
        """将 Salt grains 转换为统一模型。"""
        cpu = CPUInfo(
            model=grains.get("cpu_model", ""),
            architecture=grains.get("cpuarch", "x86_64"),
            cores=grains.get("num_cpus", 0),
            threads=grains.get("num_cpus", 0) * 2,
        )

        mem_total_mb = grains.get("mem_total", 0)
        memory = MemoryInfo(
            total_gb=round(mem_total_mb / 1024, 2),
            available_gb=round(grains.get("mem_free", 0) / 1024, 2),
        )

        disks = []
        for disk_name, disk_info in grains.get("disks", {}).items():
            disks.append(DiskInfo(
                device=disk_name,
                mount_point=disk_info.get("mount", ""),
                filesystem=disk_info.get("fstype", ""),
                total_gb=round(disk_info.get("total", 0) / 1024, 2),
                used_gb=round(disk_info.get("used", 0) / 1024, 2),
            ))

        hardware = HardwareSpec(
            hostname=grains.get("host", host),
            platform=grains.get("os", "Linux"),
            cpu=cpu,
            memory=memory,
            disks=disks,
        )

        return UnifiedDiscoveryModel(hardware=hardware)

    # ... 更多辅助方法
```

**步骤 2：注册到 DiscoveryMethod 枚举**

在 `src/opsmind/schemas/discovery.py:10` 中添加新值：

```python
class DiscoveryMethod(str, Enum):
    ANSIBLE = "ansible"
    NATIVE = "native"
    MOCK = "mock"
    AUTO = "auto"
    SALT = "salt"          # 新增
```

**步骤 3：注册到引擎选择逻辑**

在 `src/opsmind/core/engine.py` 的 `_select_engine()` 方法中添加：

```python
def _select_engine(self, target, inventory, ssh_user, ssh_key):
    # ... 现有逻辑 ...
    from opsmind.discovery.engines.salt_engine import SaltDiscoveryEngine

    # 尝试 SaltStack
    salt = SaltDiscoveryEngine()
    if salt.is_available:
        self.event_bus.emit_simple(EventType.INFO, {"engine": "salt"})
        return salt
    # ... 继续回退 ...
```

**步骤 4：编写测试**

```python
# tests/unit/test_salt_engine.py
import pytest
from opsmind.discovery.engines.salt_engine import SaltDiscoveryEngine

class TestSaltDiscoveryEngine:
    def test_method_is_salt(self):
        engine = SaltDiscoveryEngine()
        assert engine.method.value == "salt"

    def test_discover_localhost(self, mocker):
        engine = SaltDiscoveryEngine()
        # Mock subprocess.run 返回模拟 grains 数据
        mock_grains = {
            "localhost": {
                "cpu_model": "Test CPU",
                "num_cpus": 4,
                "mem_total": 8192,
                "os": "Ubuntu",
            }
        }

        mocker.patch("subprocess.run", return_value=mocker.Mock(
            returncode=0,
            stdout=json.dumps(mock_grains),
            stderr="",
        ))

        result = engine.discover_host("localhost")
        assert result.total_hosts == 1
        assert result.successful_hosts == 1
```

### 2.3 关键点

- **返回类型必须是 `DiscoveryResult`**：包含 `hosts: Dict[str, UnifiedDiscoveryModel]`
- **设置正确的 `metadata.confidence`**：真实数据源使用 `HIGH`，模拟数据使用 `LOW`
- **处理错误**：使用 `DiscoveryResult.errors` 字典记录每个主机的错误
- **`is_available` 应缓存**：参考 `AnsibleDiscoveryEngine` 中的 `_available` 缓存模式

---

## 3. 如何扩展评估规则

### 3.1 添加新的评估维度

**步骤 1：在枚举中注册维度**

```python
# src/opsmind/schemas/assessment.py
class AssessmentDimension(str, Enum):
    HARDWARE_COMPATIBILITY = "hardware_compatibility"
    SOFTWARE_SUPPORT = "software_support"
    CONFIG_COMPLEXITY = "config_complexity"
    SECURITY_BASELINE = "security_baseline"
    NETWORK_READINESS = "network_readiness"        # 新增
    DATA_PERSISTENCE = "data_persistence"          # 新增
```

**步骤 2：在可行性评估器中添加评分方法**

编辑 `src/opsmind/assessment/evaluators/feasibility.py`：

```python
class ContainerizationFeasibilityEvaluator:
    # 更新权重分配（总和必须为 1.0）
    SCORING_WEIGHTS = {
        AssessmentDimension.HARDWARE_COMPATIBILITY: 0.25,
        AssessmentDimension.SOFTWARE_SUPPORT: 0.25,
        AssessmentDimension.CONFIG_COMPLEXITY: 0.15,
        AssessmentDimension.SECURITY_BASELINE: 0.15,
        AssessmentDimension.NETWORK_READINESS: 0.10,    # 新增
        AssessmentDimension.DATA_PERSISTENCE: 0.10,     # 新增
    }

    def evaluate(self, discovery_data: UnifiedDiscoveryModel) -> FeasibilityReport:
        # 在 evaluate() 方法中添加新维度的调用
        network_score = self._assess_network_readiness(discovery_data)
        data_score = self._assess_data_persistence(discovery_data)

        dimension_scores = [
            hardware_score,
            software_score,
            config_score,
            security_score,
            network_score,     # 新增
            data_score,        # 新增
        ]
        # ... 其余逻辑不变 ...

    def _assess_network_readiness(self, data: UnifiedDiscoveryModel) -> DimensionScore:
        """评估容器化网络兼容性。"""
        score = 100.0
        findings = []
        issues = []
        recommendations = []

        # 检查网络接口数量
        iface_count = len(data.hardware.network_interfaces)
        if iface_count > 5:
            score -= 10
            findings.append(f"多个网络接口 ({iface_count}) - 需要仔细规划网络")

        # 检查是否有虚拟化网络接口（易于容器化）
        virtual_ifaces = [n for n in data.hardware.network_interfaces if n.is_virtual]
        if virtual_ifaces:
            findings.append(f"已有 {len(virtual_ifaces)} 个虚拟网卡 - 网络已部分虚拟化")

        # 检查开放端口数量
        if len(data.security.open_ports) > 20:
            score -= 15
            issues.append(f"大量开放端口 ({len(data.security.open_ports)})")
            recommendations.append("使用 Docker 端口映射精简暴露端口")

        return DimensionScore(
            dimension=AssessmentDimension.NETWORK_READINESS,
            score=max(0, score),
            weight=self.SCORING_WEIGHTS[AssessmentDimension.NETWORK_READINESS],
            findings=findings,
            issues=issues,
            recommendations=recommendations,
        )

    def _assess_data_persistence(self, data: UnifiedDiscoveryModel) -> DimensionScore:
        """评估有状态数据处理的容器化复杂度。"""
        score = 100.0
        findings = []
        issues = []
        recommendations = []

        # 检查数据库服务
        db_services = [
            s for s in data.software.services
            if s.name.lower() in ("mysqld", "postgresql", "mongod", "redis")
        ]
        if db_services:
            score -= 10
            for db in db_services:
                findings.append(f"数据库服务: {db.name}")
                recommendations.append(f"为 {db.name} 配置持久化卷")

        # 检查多挂载点
        if len(data.hardware.disks) > 3:
            score -= 10
            issues.append("多挂载点 — 需要显式卷映射")
            recommendations.append("在 docker-compose.yml 中定义所有数据卷")

        return DimensionScore(
            dimension=AssessmentDimension.DATA_PERSISTENCE,
            score=max(0, score),
            weight=self.SCORING_WEIGHTS[AssessmentDimension.DATA_PERSISTENCE],
            findings=findings,
            issues=issues,
            recommendations=recommendations,
        )
```

### 3.2 添加新的评估器

创建独立评估器文件 `src/opsmind/assessment/evaluators/performance.py`：

```python
"""性能基线评估器 — 评估工作负载对容器化性能的影响。"""

from opsmind.schemas.assessment import (
    ComplexityAssessment,
    ComplexityLevel,
)
from opsmind.schemas.discovery import UnifiedDiscoveryModel


class PerformanceEvaluator:
    """评估容器化对性能的影响。"""

    def evaluate(self, discovery_data: UnifiedDiscoveryModel) -> ComplexityAssessment:
        """评估性能影响。

        Args:
            discovery_data: 统一发现数据

        Returns:
            面向性能的复杂度评估
        """
        factors = {}
        hw = discovery_data.hardware

        # CPU 核心数影响
        if hw.cpu.cores <= 2:
            factors["低核心数 — 容器共享限制"] = 60.0
        elif hw.cpu.cores <= 4:
            factors["中等核心数"] = 30.0

        # 内存压力
        mem_util = (hw.memory.total_gb - hw.memory.available_gb) / max(hw.memory.total_gb, 0.1)
        if mem_util > 0.8:
            factors["高内存利用率"] = 70.0
        elif mem_util > 0.5:
            factors["中等内存利用率"] = 40.0

        # 磁盘 I/O 密集型判断（基于挂载点数量和总大小）
        total_disk = sum(d.total_gb for d in hw.disks)
        if total_disk > 1000:
            factors["大存储容量"] = 50.0

        if not factors:
            factors["低性能影响"] = 10.0

        score = min(sum(factors.values()) / len(factors), 100.0)

        if score < 25:
            level = ComplexityLevel.SIMPLE
        elif score < 50:
            level = ComplexityLevel.MODERATE
        elif score < 75:
            level = ComplexityLevel.COMPLEX
        else:
            level = ComplexityLevel.BLOCKER

        return ComplexityAssessment(
            level=level,
            score=round(score, 1),
            factors=factors,
            breakdown=f"性能影响评估: {score:.1f}/100",
        )
```

**注册到引擎**：在 `src/opsmind/core/engine.py:assess()` 方法中添加：

```python
def assess(self, discovery_result, detail_level="detailed"):
    from opsmind.assessment.evaluators.performance import PerformanceEvaluator
    # ... 现有评估器 ...
    performance = PerformanceEvaluator()

    for hostname, host_data in discovery_result.hosts.items():
        try:
            # ... 现有评估 ...
            perf_report = performance.evaluate(host_data)
            # 将性能报告合并到 AssessmentResult 中
            # 可扩展 AssessmentResult 添加可选字段
        except Exception as exc:
            raise AssessmentError(...)
```

### 3.3 评分规则调整指南

在 `feasibility.py` 中调整现有规则：

| 方法 | 位置 | 用途 |
|------|------|------|
| `_assess_hardware()` | 行 83 | CPU 架构、核心数、内存、磁盘空间检查 |
| `_assess_software()` | 行 140 | OS 类型/版本、内核版本、容器运行时检查 |
| `_assess_config_complexity()` | 行 215 | 服务数、遗留服务、数据库服务、SSH 检查 |
| `_assess_security()` | 行 260 | 防火墙、SELinux、补丁、端口暴露检查 |

**自定义扣分示例**：针对 GPU 工作负载添加检查：

```python
def _assess_hardware(self, data: UnifiedDiscoveryModel) -> DimensionScore:
    score = 100.0
    # ... 现有逻辑 ...

    # GPU 检查（新增）
    if "nvidia" in data.hardware.cpu.flags or any(
        "nvidia" in d.device.lower() for d in data.hardware.disks
    ):
        score -= 15
        issues.append("检测到 NVIDIA GPU — 容器化需要 nvidia-container-toolkit")
        recommendations.append("安装 nvidia-container-toolkit 启用 GPU 透传")

    return DimensionScore(...)
```

---

## 4. 如何添加新的报告格式

### 4.1 实现报告生成器接口

创建 `src/opsmind/reporting/generators/pdf.py`：

```python
"""PDF 报告生成器 — 基于 Markdown 转换。"""

import os
from typing import Dict
from datetime import datetime

from opsmind.reporting.generators.base import BaseReportGenerator
from opsmind.schemas.assessment import AssessmentResult
from opsmind.schemas.report import DetailLevel, ReportData, ReportMetadata


class PDFReportGenerator(BaseReportGenerator):
    """通过 Markdown → HTML → PDF 生成 PDF 报告。"""

    def generate(
        self,
        assessment_results: Dict[str, AssessmentResult],
        detail_level: DetailLevel,
    ) -> ReportData:
        """生成 PDF 报告数据。"""
        scores = [r.feasibility.overall_score for r in assessment_results.values()]
        avg_score = sum(scores) / len(scores) if scores else 0

        metadata = ReportMetadata(
            title="OpsMind Assessment Report (PDF)",
            generated_at=datetime.now(),
            tool_version="0.1.0",
            total_hosts=len(assessment_results),
        )

        return ReportData(
            metadata=metadata,
            executive_summary=f"评估了 {len(assessment_results)} 台主机，平均分 {avg_score:.1f}/100。",
            assessment_summary={"average_score": round(avg_score, 1)},
            host_reports=assessment_results,
        )

    def export(self, report_data: ReportData, output_path: str) -> str:
        """导出为 PDF 文件。"""
        from opsmind.reporting.generators.markdown import MarkdownReportGenerator
        from opsmind.reporting.generators.html import HTMLReportGenerator

        # 先生成 Markdown
        md_gen = MarkdownReportGenerator()
        md_data = md_gen.generate(
            report_data.host_reports,
            DetailLevel.DETAILED,
        )
        md_path = output_path.replace(".pdf", ".md")
        md_gen.export(md_data, md_path)

        # 再生成 HTML
        html_gen = HTMLReportGenerator()
        html_data = html_gen.generate(
            report_data.host_reports,
            DetailLevel.DETAILED,
        )
        html_path = output_path.replace(".pdf", ".html")
        html_gen.export(html_data, html_path)

        # HTML → PDF (需要 weasyprint)
        try:
            from weasyprint import HTML
            HTML(filename=html_path).write_pdf(output_path)
        except ImportError:
            raise RuntimeError("需要安装 weasyprint: pip install weasyprint")

        return output_path
```

**注册到引擎**：在 `src/opsmind/core/engine.py:generate_report()` 的 generators 字典中添加：

```python
generators = {
    ReportFormat.MARKDOWN: MarkdownReportGenerator,
    ReportFormat.JSON: JSONReportGenerator,
    ReportFormat.HTML: HTMLReportGenerator,
    ReportFormat.PDF: PDFReportGenerator,     # 新增
}
```

---

## 5. 代码规范

### 5.1 类型注解

**所有公开函数必须有完整的类型注解**（由 `mypy --strict` 强制执行）：

```python
# ✅ 正确
def discover_host(self, host: str) -> DiscoveryResult:
    ...

def generate(
    self, assessment_results: Dict[str, AssessmentResult], detail_level: DetailLevel
) -> ReportData:
    ...

# ❌ 错误 — 缺少返回类型
def discover_host(self, host):
    ...

# ❌ 错误 — 缺少参数类型
def generate(self, assessment_results, detail_level):
    ...
```

### 5.2 Pydantic 模型

使用 Pydantic v2 的 `BaseModel`，并利用内置验证器：

```python
from pydantic import BaseModel, Field, model_validator

class CPUInfo(BaseModel):
    model: str = Field(default="", description="CPU model name")
    cores: int = Field(default=0, ge=0)
    threads: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_cpu(self) -> "CPUInfo":
        if self.cores > 0 and self.threads > 0 and self.threads < self.cores:
            raise ValueError(f"线程数不能少于核心数")
        return self
```

### 5.3 异常处理

使用类型化异常，不抛裸字符串：

```python
# ✅ 正确
from opsmind.core.exceptions import DiscoveryError
raise DiscoveryError(
    f"发现失败: {host}",
    details={"host": host, "method": self.method.value},
)

# ❌ 错误
raise Exception("发现失败")
```

### 5.4 文档字符串

遵循 Google 风格的 docstring，包含 `Args`/`Returns`/`Raises`：

```python
def discover_host(self, host: str) -> DiscoveryResult:
    """发现单个主机。

    Args:
        host: 主机名或 IP 地址

    Returns:
        包含结构化发现数据的 DiscoveryResult

    Raises:
        DiscoveryError: 发现过程失败
        AnsibleNotAvailableError: Ansible 不可用
    """
```

### 5.5 Ruff Lint 规则

项目的 Ruff 配置（`pyproject.toml:83`）启用了以下规则：

```toml
[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM"]
# E: pycodestyle errors
# F: Pyflakes (未使用变量、未定义名称等)
# W: pycodestyle warnings
# I: isort (导入排序)
# N: pep8-naming (命名规范)
# UP: pyupgrade (使用更新的 Python 语法)
# B: flake8-bugbear (常见错误)
# SIM: flake8-simplify (代码简化建议)
```

**提交前运行**：
```bash
ruff check src/opsmind/
ruff format src/opsmind/    # 自动格式化
```

### 5.6 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块文件 | `snake_case.py` | `ansible_engine.py` |
| 类名 | `PascalCase` | `ContainerizationFeasibilityEvaluator` |
| 函数/方法 | `snake_case` | `discover_host()`, `generate_report()` |
| 私有方法 | `_snake_case` | `_assess_hardware()`, `_select_engine()` |
| 常量 | `UPPER_SNAKE_CASE` | `SCORING_WEIGHTS` |
| 枚举值 | `UPPER_SNAKE_CASE` | `HARDWARE_COMPATIBILITY` |

---

## 6. 测试要求

### 6.1 测试结构

```
tests/
├── __init__.py
├── fixtures/
│   ├── __init__.py
│   └── ansible_facts.json            # Ansible facts 测试数据
├── unit/
│   ├── __init__.py
│   ├── test_schemas.py               # Pydantic 模型验证测试
│   ├── test_adapter.py               # AnsibleFactAdapter 测试
│   ├── test_engine.py                # OpsMindEngine 测试
│   └── test_evaluators.py            # 评估器测试
└── integration/
    ├── __init__.py
    └── test_pipeline.py              # 端到端流水线测试
```

### 6.2 运行测试

```bash
# 全部单元测试
pytest tests/unit/ -v

# 全部集成测试
pytest tests/integration/ -v

# 全部测试 + 覆盖率
pytest --cov=opsmind tests/ -v

# 只运行标记为 slow 的测试
pytest -m slow -v

# 只运行需要 Ansible 的测试
pytest -m ansible -v

# 指定单个测试类
pytest tests/unit/test_evaluators.py::TestFeasibilityEvaluator -v

# 指定单个测试方法
pytest tests/unit/test_engine.py::TestOpsMindEngine::test_discover_mock -v
```

### 6.3 测试编写规范

**每个新增组件必须有测试**。参考现有测试模式：

**模型验证测试**（`tests/unit/test_schemas.py`）：
```python
class TestDiscoverySchemas:
    def test_cpu_info_valid(self):
        """有效数据应正确创建。"""
        cpu = CPUInfo(model="Test CPU", cores=4, threads=8)
        assert cpu.cores == 4
        assert cpu.threads == 8

    def test_cpu_info_threads_not_less_than_cores(self):
        """违反模型约束应抛出 ValidationError。"""
        with pytest.raises(ValidationError):
            CPUInfo(model="Bad CPU", cores=8, threads=4)
```

**评估器测试**（`tests/unit/test_evaluators.py`）：
```python
@pytest.fixture
def legacy_candidate():
    """获取用于测试的遗留系统数据。"""
    engine = MockDiscoveryEngine(profile="legacy-centos")
    result = engine.discover_host("legacy-centos")
    return list(result.hosts.values())[0]

class TestFeasibilityEvaluator:
    def test_legacy_system_assessment(self, legacy_candidate):
        """遗留系统应有较低分数。"""
        report = self.evaluator.evaluate(legacy_candidate)
        assert 0 <= report.overall_score <= 100
        assert report.complexity in (
            ComplexityLevel.MODERATE,
            ComplexityLevel.COMPLEX,
            ComplexityLevel.BLOCKER,
        )
        assert len(report.dimension_scores) == 4

    def test_dimension_scores_present(self, legacy_candidate):
        """应包含全部4个维度的评分。"""
        report = self.evaluator.evaluate(legacy_candidate)
        dims = {ds.dimension.value for ds in report.dimension_scores}
        assert "hardware_compatibility" in dims
        assert "software_support" in dims
        assert "config_complexity" in dims
        assert "security_baseline" in dims
```

**集成测试**（`tests/integration/test_pipeline.py`）：
```python
@pytest.mark.integration
class TestFullPipeline:
    def test_full_pipeline_with_remediation(self):
        """完整流水线生成所有预期产物。"""
        result = self.engine.run_pipeline(
            "localhost",
            method="mock",
            report_format="json",
            output_dir=self.tmpdir,
            generate_remediation=True,
        )
        assert "discovery" in result
        assert "assessment" in result
        assert "report" in result
        assert "remediation" in result
        assert "docker" in result["remediation"]
        assert "migration_plan" in result["remediation"]
```

### 6.4 pytest 标记

```python
# 定义在 pyproject.toml:54
markers = [
    "unit: 单元测试",
    "integration: 集成测试",
    "slow: 慢速测试（性能基准）",
    "ansible: 需要 Ansible 的测试",
]
```

### 6.5 覆盖率要求

编辑 `pyproject.toml` 中的覆盖率配置：

```toml
[tool.coverage.report]
fail_under = 80        # CI 中低于 80% 构建失败
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]

[tool.coverage.run]
source = ["opsmind"]
branch = true
```

---

## 附录：开发环境配置

```bash
# 创建虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate

# 安装开发依赖
pip install -e ".[dev]"

# 安装所有可选依赖
pip install -e .
pip install ansible-core ansible-runner weasyprint

# 运行类型检查
mypy src/opsmind/

# 运行 lint
ruff check src/opsmind/

# 运行完整测试套件
pytest --cov=opsmind tests/ -v

# 提交前检查清单
mypy src/opsmind/ && ruff check src/opsmind/ && pytest tests/ -v
```

**常见开发命令速查**：

```bash
# 只检查类型
mypy src/opsmind/

# 自动修复 lint 问题
ruff check --fix src/opsmind/

# 快速运行所有测试（无覆盖率）
pytest tests/ -x -v

# 生成 HTML 覆盖率报告
pytest --cov=opsmind --cov-report=html tests/
open htmlcov/index.html
```
