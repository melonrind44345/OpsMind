# OpsMind Architecture Design Document

> **Version**: 0.1.0 | **Last Updated**: 2026-05-16

---

## Table of Contents

- [Part I: Technical Perspective](#part-i-technical-perspective)
  - [Module Hierarchy](#module-hierarchy)
  - [Data Flow](#data-flow)
  - [Interface Definitions](#interface-definitions)
  - [Schema Layer](#schema-layer)
  - [Event System](#event-system)
  - [Error Handling Strategy](#error-handling-strategy)
- [Part II: Business Perspective](#part-ii-business-perspective)
  - [Problem Space](#problem-space)
  - [Value Stream](#value-stream)
  - [User Personas](#user-personas)
  - [Workflow Stages](#workflow-stages)
- [Part III: Extension Points](#part-iii-extension-points)

---

## Part I: Technical Perspective

### Module Hierarchy

OpsMind follows a **five-tier layered architecture** with vertical domain boundaries:

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLI Layer (Typer + Rich)                       │
│  src/opsmind/cli/main.py                                         │
│  Commands: discover | assess | report | generate | pipeline      │
├─────────────────────────────────────────────────────────────────┤
│                   Orchestration Layer                             │
│  src/opsmind/core/engine.py    →  OpsMindEngine                  │
│  src/opsmind/core/events.py    →  EventBus, EventType            │
│  src/opsmind/core/exceptions.py → OpsMindError hierarchy         │
├────────────────┬──────────────────┬───────────────┬──────────────┤
│   Discovery    │   Assessment     │  Reporting    │ Remediation  │
│   Engines      │   Evaluators     │  Generators   │  Generators  │
├────────────────┼──────────────────┼───────────────┼──────────────┤
│   Adapters     │                  │  Visualizers  │  Templates   │
│   Collectors   │                  │               │              │
├────────────────┴──────────────────┴───────────────┴──────────────┤
│                    Schema Layer (Pydantic v2)                      │
│  discovery.py → DiscoveryResult, UnifiedDiscoveryModel, CPUInfo   │
│  assessment.py → AssessmentResult, FeasibilityReport, etc.       │
│  report.py → ReportData, ReportFormat, DetailLevel                │
├──────────────────────────────────────────────────────────────────┤
│                     Utility Layer                                  │
│  ansible_utils.py | validation.py | logging.py                    │
└──────────────────────────────────────────────────────────────────┘
```

#### Layer Responsibilities

| Layer | Key Classes | Responsibility |
|-------|------------|----------------|
| **CLI** | `app` (Typer), `console` (Rich) | User input parsing, progress display, output formatting |
| **Orchestration** | `OpsMindEngine` (`engine.py:19`) | Workflow coordination, engine selection, phase ordering |
| **Discovery** | `BaseDiscoveryEngine`, `AnsibleFactAdapter` | Host fact collection via Ansible/Native/Mock |
| **Assessment** | `ContainerizationFeasibilityEvaluator` (`feasibility.py:20`), `ComplexityEvaluator` (`complexity.py:14`), `SecurityEvaluator` (`security.py:9`) | Multi-dimension containerization scoring |
| **Reporting** | `BaseReportGenerator`, `MarkdownReportGenerator` (`markdown.py:13`), `JSONReportGenerator` (`json.py:13`), `HTMLReportGenerator` (`html.py:12`) | Report generation in MD/JSON/HTML |
| **Remediation** | `DockerGenerator` (`docker.py:11`), `MigrationPlanGenerator` (`migration_plan.py:10`) | Docker artifacts and migration plans |
| **Schema** | Pydantic models in `schemas/*.py` | Type-safe data exchange with built-in validation |
| **Utility** | `ansiible_utils.py`, `validation.py`, `logging.py` | Cross-cutting concerns |

### Data Flow

The complete data flow through the system follows the **D-A-R-R pipeline**:

```
User Input (CLI argv)
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│ Phase 1: DISCOVERY                                                │
│                                                                   │
│  target ──► OpsMindEngine.discover()  (engine.py:40)              │
│               │                                                   │
│               ├─ _resolve_method() → DiscoveryMethod enum         │
│               └─ _select_engine()  → Ansible / Native / Mock      │
│                                                                   │
│  Engine execution:                                                │
│    AnsibleDiscoveryEngine.discover_host() (ansible_engine.py:91)  │
│      └─ ansible-playbook → raw facts → AnsibleFactAdapter         │
│    NativeDiscoveryEngine.discover_host() (native_engine.py:51)    │
│      └─ psutil + platform → direct model construction             │
│    MockDiscoveryEngine.discover_host() (mock_engine.py:134)       │
│      └─ MOCK_PROFILES dict → _build_unified()                     │
│                                                                   │
│  Output: DiscoveryResult {                                        │
│    hosts: Dict[str, UnifiedDiscoveryModel],                       │
│    total_hosts, successful_hosts, failed_hosts,                   │
│    errors: Dict[str, List[str]]                                   │
│  }                                                                │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│ Phase 2: ASSESSMENT                                               │
│                                                                   │
│  DiscoveryResult ──► OpsMindEngine.assess()  (engine.py:110)      │
│                       │                                           │
│                       ▼                                           │
│  For each hostname, host_data in discovery_result.hosts.items():  │
│    ├─ ContainerizationFeasibilityEvaluator.evaluate()             │
│    │   (feasibility.py:37)                                        │
│    │   ├─ _assess_hardware()        → DimensionScore (w=0.30)     │
│    │   ├─ _assess_software()        → DimensionScore (w=0.30)     │
│    │   ├─ _assess_config_complexity() → DimensionScore (w=0.20)   │
│    │   └─ _assess_security()        → DimensionScore (w=0.20)     │
│    │                                                              │
│    ├─ ComplexityEvaluator.evaluate()  (complexity.py:17)          │
│    │   ├─ _assess_complexity()      → ComplexityAssessment        │
│    │   ├─ _recommend_sizing()       → ResourceSizing              │
│    │   └─ _recommend_strategy()     → MigrationStrategy           │
│    │                                                              │
│    └─ SecurityEvaluator.evaluate()   (security.py:12)             │
│                                                                   │
│  Output: Dict[str, AssessmentResult] {                            │
│    host → { feasibility, complexity, resource_sizing,             │
│              migration_strategy, data_source }                    │
│  }                                                                │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│ Phase 3: REPORTING                                                │
│                                                                   │
│  Dict[str, AssessmentResult] ──► OpsMindEngine.generate_report()  │
│                                   (engine.py:157)                 │
│                                   │                               │
│                                   ▼                               │
│  Format dispatch via generators dict:                             │
│    MARKDOWN → MarkdownReportGenerator.generate()                  │
│    JSON     → JSONReportGenerator.generate()                      │
│    HTML     → HTMLReportGenerator.generate()                      │
│               │                                                   │
│               ▼                                                   │
│  Output: ReportData { metadata, executive_summary, sections[] }   │
│  Written to: opsmind_report.{md|json|html}                        │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼  (if --remediation / generate_remediation())
┌──────────────────────────────────────────────────────────────────┐
│ Phase 4: REMEDIATION                                              │
│                                                                   │
│  Dict[str, AssessmentResult] ──► generate_remediation() (l.214)   │
│                                   │                               │
│                                   ▼                               │
│  DockerGenerator.generate()  (docker.py:17)                       │
│    ├─ _generate_dockerfile()        → Dockerfile                  │
│    ├─ _generate_compose()           → docker-compose.yml          │
│    ├─ _generate_dockerignore()      → .dockerignore               │
│    └─ _generate_build_script()      → build.sh (chmod 755)        │
│                                                                   │
│  MigrationPlanGenerator.generate()  (migration_plan.py:16)        │
│    ├─ _generate_plan()              → {host}_migration_plan.md    │
│    └─ _generate_summary_plan()      → 00_migration_overview.md    │
│                                                                   │
│  Output: Dict[str, List[str]] (artifact type → file paths)        │
└──────────────────────────────────────────────────────────────────┘
```

### Interface Definitions

#### 1. Discovery Engine Interface

All discovery engines implement `BaseDiscoveryEngine` (`src/opsmind/discovery/engines/base.py:9`):

```python
class BaseDiscoveryEngine(ABC):
    @property
    @abstractmethod
    def method(self) -> DiscoveryMethod:
        """Return the discovery method this engine implements."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this engine is available on the current system."""
        ...

    @abstractmethod
    def discover_host(self, host: str) -> DiscoveryResult:
        """Discover a single host and return structured result."""
        ...

    @abstractmethod
    def discover_group(self, hosts: List[str], parallel: bool = True) -> DiscoveryResult:
        """Discover multiple hosts, optionally in parallel."""
        ...
```

| Implementation | File | Method | Scope |
|---------------|------|--------|-------|
| `AnsibleDiscoveryEngine` | `ansible_engine.py:29` | `ansible` | Local + Remote via SSH |
| `NativeDiscoveryEngine` | `native_engine.py:32` | `native` | Localhost only (psutil) |
| `MockDiscoveryEngine` | `mock_engine.py:29` | `mock` | Simulated (3 profiles) |

#### 2. Data Adapter Interface

```python
# src/opsmind/discovery/adapters/base_adapter.py:9
class BaseAdapter(ABC):
    @abstractmethod
    def to_unified_model(self, raw_data: Dict[str, Any]) -> UnifiedDiscoveryModel:
        """Convert raw discovery data to unified model."""
        ...
```

The sole implementation `AnsibleFactAdapter` (`ansible_adapter.py:26`) handles the complex mapping from Ansible's nested fact structure (`ansible_*` keys) to OpsMind's standardized `UnifiedDiscoveryModel` with safe type conversion (`_safe_get`, `_safe_int`, `_safe_float`).

#### 3. Report Generator Interface

```python
# src/opsmind/reporting/generators/base.py:10
class BaseReportGenerator(ABC):
    def __init__(self, output_dir: str | None = None) -> None:
        self.output_dir = output_dir

    @abstractmethod
    def generate(
        self, assessment_results: Dict[str, AssessmentResult], detail_level: DetailLevel
    ) -> ReportData:
        """Generate report data from assessment results."""
        ...

    @abstractmethod
    def export(self, report_data: ReportData, output_path: str) -> str:
        """Export report to a file."""
        ...
```

| Generator | File | Format | Key Features |
|-----------|------|--------|-------------|
| `MarkdownReportGenerator` | `markdown.py:13` | `.md` | Score bars, dimension tables, per-host sections |
| `JSONReportGenerator` | `json.py:13` | `.json` | Full structured data for automation |
| `HTMLReportGenerator` | `html.py:12` | `.html` | Self-contained CSS, responsive cards, color-coded scores |

#### 4. Engine Orchestrator Interface

`OpsMindEngine` (`src/opsmind/core/engine.py:19`) is the central coordinator:

```python
class OpsMindEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None: ...

    # Core pipeline methods
    def discover(self, target, method, inventory, ssh_user, ssh_key, parallel) -> DiscoveryResult: ...
    def assess(self, discovery_result, detail_level) -> Dict[str, AssessmentResult]: ...
    def generate_report(self, assessment_results, format, detail_level, output_dir) -> ReportData: ...
    def generate_remediation(self, assessment_results, output_dir, optimize) -> Dict[str, List[str]]: ...

    # Convenience: runs all four phases in sequence
    def run_pipeline(self, target, method, report_format, detail_level,
                     output_dir, generate_remediation, optimize) -> Dict[str, Any]: ...

    # Internal
    def _validate_target(self, target) -> None: ...
    def _resolve_method(self, method) -> DiscoveryMethod: ...
    def _select_engine(self, target, inventory, ssh_user, ssh_key) -> BaseDiscoveryEngine: ...
```

#### 5. Engine Auto-Selection

When `method="auto"`, `_select_engine()` (`engine.py:320`) follows this fallback chain:

```
For localhost:
  AnsibleDiscoveryEngine.is_available → YES → use it
                                      → NO  → NativeDiscoveryEngine

For remote hosts:
  AnsibleDiscoveryEngine.is_available → YES → use it
                                      → NO  → MockDiscoveryEngine (emits ENGINE_FALLBACK event)
```

### Schema Layer

OpsMind uses **Pydantic v2** models throughout. All schemas include built-in validators.

#### Discovery Schemas (`src/opsmind/schemas/discovery.py`)

Core enumerations and models:

```python
class DiscoveryMethod(str, Enum):   # ansible | native | mock | auto
class DataSource(str, Enum):        # ansible.setup | native.detection | mock.data | ...
class ConfidenceLevel(str, Enum):   # high | medium | low | estimated

# Hardware
class CPUInfo(BaseModel):           # model, architecture, cores, threads, frequency_mhz, flags
class MemoryInfo(BaseModel):        # total_gb, available_gb, swap_total_gb, swap_available_gb
class DiskInfo(BaseModel):          # device, mount_point, filesystem, total_gb, used_gb, is_ssd
class NetworkInterface(BaseModel):  # name, mac_address, ipv4_addresses, is_up, is_virtual
class HardwareSpec(BaseModel):      # hostname, platform, cpu, memory, disks, network_interfaces

# Software
class SoftwarePackage(BaseModel):   # name, version, architecture, vendor
class ServiceInfo(BaseModel):       # name, state, enabled, pid
class SoftwareEnvironment(BaseModel): # os_name, os_version, os_family, kernel, packages, services

# Security
class SecurityAssessment(BaseModel): # os_uptodate, firewall_active, selinux_enforcing, open_ports

# Unified
class UnifiedDiscoveryModel(BaseModel):
    hardware: HardwareSpec
    software: SoftwareEnvironment
    security: SecurityAssessment
    metadata: DiscoveryMetadata
    raw_facts: Dict[str, Any]

class DiscoveryResult(BaseModel):
    hosts: Dict[str, UnifiedDiscoveryModel]
    total_hosts, successful_hosts, failed_hosts: int
    total_duration_ms: float
    errors: Dict[str, List[str]]
```

Built-in validators examples:
- `CPUInfo`: `threads >= cores` check (`discovery.py:50`)
- `MemoryInfo`: `available_gb <= total_gb` check (`discovery.py:67`)

#### Assessment Schemas (`src/opsmind/schemas/assessment.py`)

```python
class AssessmentDimension(str, Enum):  # hardware_compatibility | software_support | ...
class ComplexityLevel(str, Enum):      # simple | moderate | complex | blocker
class RiskLevel(str, Enum):            # low | medium | high | critical

class DimensionScore(BaseModel):       # dimension, score(0-100), weight, findings, issues
class FeasibilityReport(BaseModel):    # overall_score, dimension_scores[], complexity, risk_level
class ComplexityAssessment(BaseModel): # level, score, factors, estimated_effort_days, skills
class ResourceSizing(BaseModel):       # cpu_cores, memory_gb, storage_gb, replicas, rationale
class MigrationStrategy(BaseModel):    # strategy_type, phases[], risks[], rollback_strategy

class AssessmentResult(BaseModel):
    host: str
    feasibility: FeasibilityReport
    complexity: ComplexityAssessment
    resource_sizing: ResourceSizing
    migration_strategy: MigrationStrategy
    assessed_at: datetime
    data_source: str
```

#### Report Schemas (`src/opsmind/schemas/report.py`)

```python
class ReportFormat(str, Enum):    # markdown | json | html
class DetailLevel(str, Enum):     # executive | summary | detailed | raw

class ReportMetadata(BaseModel):  # title, generated_at, tool_version, total_hosts
class ReportSection(BaseModel):   # title, content, subsections[]
class ReportData(BaseModel):      # metadata, executive_summary, sections[], host_reports
class ReportComparison(BaseModel):# before_report, after_report, score_delta, changes[]
```

### Event System

The **singleton** `EventBus` (`src/opsmind/core/events.py:58`) enables decoupled workflow observability:

```python
class EventType(Enum):
    # Discovery
    DISCOVERY_STARTED      = "discovery.started"
    DISCOVERY_HOST_STARTED  = "discovery.host.started"
    DISCOVERY_HOST_COMPLETED = "discovery.host.completed"
    DISCOVERY_HOST_FAILED   = "discovery.host.failed"
    DISCOVERY_COMPLETED     = "discovery.completed"

    # Engine
    ENGINE_FALLBACK = "engine.fallback"
    ENGINE_RETRY    = "engine.retry"
    ENGINE_DEGRADED = "engine.degraded"

    # Assessment
    ASSESSMENT_STARTED   = "assessment.started"
    ASSESSMENT_COMPLETED = "assessment.completed"

    # Reporting & Remediation
    REPORT_GENERATION_STARTED    = "report.generation.started"
    REPORT_GENERATION_COMPLETED  = "report.generation.completed"
    REMEDIATION_STARTED  = "remediation.started"
    REMEDIATION_COMPLETED = "remediation.completed"

    # General
    WORKFLOW_STEP = "workflow.step"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
```

Usage example from `engine.py`:
```python
self.event_bus.emit_simple(EventType.DISCOVERY_STARTED, {"target": target, "method": method_enum.value})
self.event_bus.emit_simple(EventType.ENGINE_FALLBACK, {"from": "ansible", "to": "native"})
```

### Error Handling Strategy

The exception hierarchy (`src/opsmind/core/exceptions.py`) provides typed, recoverable error handling:

```
OpsMindError (base, code="OPSMIND_ERR", recoverable=False)
├── DiscoveryError (code="DISC_ERR", recoverable=True)
│   ├── AnsibleError (code="ANS_ERR")
│   │   ├── AnsibleNotAvailableError (code="ANS_NOT_FOUND", severity=WARNING)
│   │   └── SSHConnectionError (code="ANS_SSH_FAIL")
│   └── NativeDiscoveryError (code="NAT_ERR", severity=WARNING)
├── AssessmentError (code="ASMT_ERR", recoverable=False)
├── ReportGenerationError (code="REP_ERR", recoverable=True)
├── RemediationError (code="REMD_ERR", recoverable=True)
└── ValidationError (code="VAL_ERR", severity=WARNING)
```

Each exception carries `message`, `code`, `severity`, `details: dict`, and `recoverable: bool`.

**Fallback chain for error recovery:**

| Level | Failure | Fallback | User Impact |
|-------|---------|----------|-------------|
| 1 | Ansible unavailable | Native discovery | Transparent (localhost) |
| 2 | Native unavailable | Mock data + warning | Data marked "LOW confidence" |
| 3 | Critical data missing | Heuristic inference | Data marked "ESTIMATED" |
| 4 | All methods fail | Graceful error | Clear error message + diagnostics |

---

## Part II: Business Perspective

### Problem Space

Organizations modernizing legacy infrastructure face four fundamental challenges that OpsMind addresses:

| Problem | Business Impact | OpsMind's Solution |
|---------|----------------|-------------------|
| **Unknown system state** | No central inventory of OS versions, packages, services across hundreds of servers | Automated multi-host discovery with typed output (`UnifiedDiscoveryModel`) |
| **Unclear migration feasibility** | Can't estimate containerization effort → budget uncertainty | Weighted multi-dimensional 0-100 scoring with rationale |
| **Risk of missed dependencies** | Failed migrations due to hidden configs, legacy services | Deep discovery: mount points, open ports, SELinux, kernel version |
| **No actionable output** | Assessment without artifacts = wasted consulting engagement | Generated Dockerfile, docker-compose.yml, phased migration plans |

### Value Stream

The OpsMind value stream is defined by the **Discover → Assess → Report → Remediate** pipeline:

```
Input: Unknown Legacy Host(s)              Output: Containerized System
    │                                            ▲
    ▼                                            │
┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  DISCOVER   │  │   ASSESS    │  │   REPORT   │ │
│             │  │             │  │            │ │
│ "What do we │─►│ "Can it be  │─►│ "What's the│─┤
│  have?"     │  │  moved?"    │  │  plan?"    │ │
└─────────────┘  └─────────────┘  └────────────┘ │
                                                  │
                   ┌─────────────┐                │
                   │  REMEDIATE  │────────────────┘
                   │             │
                   │ "Build the  │
                   │  target"    │
                   └─────────────┘
```

**Value delivered at each stage:**

| Stage | Business Question | Delivered Artifact | Stakeholder |
|-------|------------------|-------------------|-------------|
| 1. Discover | "What do we have?" | `DiscoveryResult` — typed hardware, software, security inventory | DevOps, Infra |
| 2. Assess | "Can it be containerized?" | `FeasibilityReport` — 0-100 score with per-dimension breakdown | Architects, Leadership |
| 3. Report | "What's the plan?" | `ReportData` — MD/JSON/HTML with recommendations | All stakeholders |
| 4. Remediate | "Build the target" | Dockerfile, compose, migration plan, build scripts | DevOps, Developers |

### User Personas

| Persona | Primary Goal | Key Commands |
|---------|-------------|-------------|
| **DevOps Engineer** | Quickly assess fleet for container migration | `opsmind pipeline web-servers -m ansible --remediation` |
| **Solution Architect** | Get feasibility report for planning & budgeting | `opsmind pipeline <host> -f html -d executive` |
| **Security Lead** | Understand security gaps before migration | `opsmind discover <host> && opsmind assess -d detailed` |
| **Developer** | Generate working Dockerfile from existing server | `opsmind pipeline localhost -r` |

### Workflow Stages (Business View)

Each pipeline phase answers a specific business question and maps to a concrete decision point:

```
Phase 1: DISCOVERY
  Question: "What servers, OS versions, packages, and services do we have?"
  Decision: Inventory completeness — are we missing anything?

Phase 2: ASSESSMENT
  Question: "Which servers are candidates for containerization, and which need refactoring?"
  Decision: Go/no-go per host based on feasibility score and complexity level

Phase 3: REPORTING
  Question: "What does leadership need to approve the migration budget?"
  Decision: Resource allocation and timeline approval

Phase 4: REMEDIATION
  Question: "How do we actually build the containers?"
  Decision: Execution — who does what, in what order
```

### Scoring Model (opsmind-weighted-v1)

The assessment algorithm (`feasibility.py:30`) uses these weights:

| Dimension | Weight | What It Evaluates |
|-----------|--------|-------------------|
| Hardware Compatibility | 30% | CPU arch, cores, memory, disk space |
| Software Support | 30% | OS type/version, kernel, package ecosystem |
| Configuration Complexity | 20% | Services, dependencies, mount points, stateful services |
| Security Baseline | 20% | Firewall, SELinux, pending updates, open ports |

**Score interpretation:**

| Score Range | Complexity | Risk | Recommended Strategy |
|------------|-----------|------|---------------------|
| 80-100 | SIMPLE | LOW | `rehost` — lift and shift |
| 60-79 | MODERATE | MEDIUM | `rehost` with minor config changes |
| 40-59 | COMPLEX | HIGH | `refactor` — OS upgrade + app changes |
| 0-39 | BLOCKER | CRITICAL | `rearchitect` — full rebuild |

---

## Part III: Extension Points

OpsMind is designed with explicit extension points for each layer:

| Extension | Interface to Implement | Registration |
|-----------|----------------------|-------------|
| New discovery engine | `BaseDiscoveryEngine` (`engines/base.py:9`) | Add to `_select_engine()` in `engine.py` |
| New fact adapter | `BaseAdapter` (`adapters/base_adapter.py:9`) | Use in new engine's `discover_host()` |
| New evaluator | Standalone class (no base required) | Add to `engine.assess()` method |
| New report format | `BaseReportGenerator` (`reporting/generators/base.py:10`) | Add to generators dict in `engine.generate_report()` |
| New remediation type | Standalone generator class | Add to `engine.generate_remediation()` |
| Custom event handler | `EventHandler = Callable[[Event], None]` | `EventBus().subscribe(event_type, handler)` |

### Directory Map

```
src/opsmind/
├── __init__.py
├── cli/main.py                          # 7 Typer commands, ~750 lines
├── core/
│   ├── engine.py                        # OpsMindEngine (353 lines)
│   ├── events.py                        # EventBus singleton (114 lines)
│   └── exceptions.py                    # 10 exception classes (174 lines)
├── schemas/
│   ├── discovery.py                     # 14 Pydantic models (197 lines)
│   ├── assessment.py                    # 12 Pydantic models (115 lines)
│   └── report.py                        # 6 Pydantic models (74 lines)
├── discovery/
│   ├── engines/
│   │   ├── base.py                      # ABC (52 lines)
│   │   ├── ansible_engine.py            # SSH + playbook execution (455 lines)
│   │   ├── native_engine.py             # psutil detection (258 lines)
│   │   └── mock_engine.py               # 3 built-in profiles (286 lines)
│   ├── adapters/
│   │   ├── base_adapter.py              # ABC (16 lines)
│   │   └── ansible_adapter.py           # Fact mapping (310 lines)
│   └── collectors/
│       ├── hardware.py                  # DMI/SSD detection
│       ├── software.py                  # Runtime/version detection
│       └── security.py                  # Port/SSH/update scanning
├── assessment/evaluators/
│   ├── feasibility.py                   # 4-dimension scorer (372 lines)
│   ├── complexity.py                    # Effort & sizing (266 lines)
│   └── security.py                      # Security posture (73 lines)
├── reporting/generators/
│   ├── base.py                          # ABC (27 lines)
│   ├── markdown.py                      # MD with score bars (255 lines)
│   ├── json.py                          # Structured JSON (128 lines)
│   └── html.py                          # Self-contained HTML (203 lines)
├── remediation/generators/
│   ├── docker.py                        # Dockerfile + compose (253 lines)
│   └── migration_plan.py                # Phased plans (176 lines)
└── utils/
    ├── ansible_utils.py                 # Ansible helpers (137 lines)
    ├── validation.py                    # Input validation (120 lines)
    └── logging.py                       # Structured JSON logging (93 lines)
```
