"""Pydantic models for discovery data."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class DiscoveryMethod(StrEnum):
    """Supported discovery methods."""

    ANSIBLE = "ansible"
    NATIVE = "native"
    MOCK = "mock"
    AUTO = "auto"


class DataSource(StrEnum):
    """Origin of discovered data."""

    ANSIBLE_SETUP = "ansible.setup"
    ANSIBLE_CUSTOM = "ansible.custom_playbook"
    NATIVE_DETECTION = "native.detection"
    MOCK_DATA = "mock.data"
    HEURISTIC_INFERENCE = "heuristic.inference"


class ConfidenceLevel(StrEnum):
    """Confidence level of the data."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ESTIMATED = "estimated"


class CPUInfo(BaseModel):
    """CPU hardware information."""

    model: str = Field(default="", description="CPU model name")
    architecture: str = Field(default="", description="CPU architecture (x86_64, aarch64, etc.)")
    cores: int = Field(default=0, ge=0, description="Number of physical cores")
    threads: int = Field(default=0, ge=0, description="Number of logical threads")
    frequency_mhz: float | None = Field(default=None, description="CPU frequency in MHz")
    flags: list[str] = Field(default_factory=list, description="CPU feature flags")
    cache_size_kb: int | None = Field(default=None, description="CPU cache size in KB")
    virtualization: str | None = Field(default=None, description="Virtualization type if applicable")

    @model_validator(mode="after")
    def validate_cpu(self) -> "CPUInfo":
        if self.cores > 0 and self.threads > 0 and self.threads < self.cores:
            raise ValueError(f"Threads ({self.threads}) cannot be less than cores ({self.cores})")
        return self


class MemoryInfo(BaseModel):
    """Memory hardware information."""

    total_gb: float = Field(default=0.0, ge=0.0, description="Total memory in GB")
    available_gb: float = Field(default=0.0, ge=0.0, description="Available memory in GB")
    swap_total_gb: float = Field(default=0.0, ge=0.0, description="Total swap in GB")
    swap_available_gb: float = Field(default=0.0, ge=0.0, description="Available swap in GB")
    memory_type: str | None = Field(default=None, description="Memory type (DDR3, DDR4, etc.)")

    @model_validator(mode="after")
    def validate_memory(self) -> "MemoryInfo":
        if self.available_gb > self.total_gb > 0:
            raise ValueError(f"Available memory ({self.available_gb}GB) exceeds total ({self.total_gb}GB)")
        return self


class DiskInfo(BaseModel):
    """Disk storage information."""

    device: str = Field(default="", description="Device path")
    mount_point: str = Field(default="", description="Mount point")
    filesystem: str = Field(default="", description="Filesystem type")
    total_gb: float = Field(default=0.0, ge=0.0, description="Total size in GB")
    used_gb: float = Field(default=0.0, ge=0.0, description="Used space in GB")
    available_gb: float = Field(default=0.0, ge=0.0, description="Available space in GB")
    is_ssd: bool | None = Field(default=None, description="Whether the disk is an SSD")
    mount_options: list[str] = Field(default_factory=list, description="Mount options")


class NetworkInterface(BaseModel):
    """Network interface information."""

    name: str = Field(default="", description="Interface name")
    mac_address: str = Field(default="", description="MAC address")
    ipv4_addresses: list[str] = Field(default_factory=list, description="IPv4 addresses")
    ipv6_addresses: list[str] = Field(default_factory=list, description="IPv6 addresses")
    speed_mbps: int | None = Field(default=None, description="Interface speed in Mbps")
    is_up: bool = Field(default=True, description="Whether the interface is up")
    is_virtual: bool = Field(default=False, description="Whether the interface is virtual")


class HardwareSpec(BaseModel):
    """Complete hardware specification."""

    hostname: str = Field(default="", description="System hostname")
    platform: str = Field(default="", description="Platform (Linux, Windows, etc.)")
    cpu: CPUInfo = Field(default_factory=CPUInfo, description="CPU information")
    memory: MemoryInfo = Field(default_factory=MemoryInfo, description="Memory information")
    disks: list[DiskInfo] = Field(default_factory=list, description="Disk information")
    network_interfaces: list[NetworkInterface] = Field(default_factory=list, description="Network interfaces")
    system_vendor: str | None = Field(default=None, description="System vendor")
    system_model: str | None = Field(default=None, description="System model")
    bios_version: str | None = Field(default=None, description="BIOS version")
    uptime_seconds: int | None = Field(default=None, description="System uptime in seconds")


class SoftwarePackage(BaseModel):
    """Software package information."""

    name: str = Field(default="", description="Package name")
    version: str = Field(default="", description="Package version")
    architecture: str = Field(default="", description="Package architecture")
    vendor: str | None = Field(default=None, description="Package vendor/provider")
    description: str | None = Field(default=None, description="Package description")
    install_date: datetime | None = Field(default=None, description="Installation date")


class ServiceInfo(BaseModel):
    """System service information."""

    name: str = Field(default="", description="Service name")
    state: str = Field(default="", description="Service state (running, stopped, etc.)")
    enabled: bool = Field(default=False, description="Whether service is enabled on boot")
    load_state: str | None = Field(default=None, description="Service load state")
    description: str | None = Field(default=None, description="Service description")
    pid: int | None = Field(default=None, description="Process ID if running")


class SoftwareEnvironment(BaseModel):
    """Software environment information."""

    os_name: str = Field(default="", description="Operating system name")
    os_version: str = Field(default="", description="Operating system version")
    os_family: str = Field(default="", description="OS family (RedHat, Debian, etc.)")
    kernel: str = Field(default="", description="Kernel version")
    packages: list[SoftwarePackage] = Field(default_factory=list, description="Installed packages")
    services: list[ServiceInfo] = Field(default_factory=list, description="System services")
    run_level: str | None = Field(default=None, description="System run level")
    selinux_enabled: bool | None = Field(default=None, description="SELinux status")
    firewall_enabled: bool | None = Field(default=None, description="Firewall status")
    hostname: str = Field(default="", description="System hostname")


class SecurityAssessment(BaseModel):
    """Security baseline assessment."""

    os_uptodate: bool = Field(default=False, description="Whether OS packages are up to date")
    firewall_active: bool = Field(default=False, description="Whether firewall is active")
    selinux_enforcing: bool | None = Field(default=None, description="Whether SELinux is enforcing")
    ssh_config_secure: bool = Field(default=False, description="Whether SSH configuration is secure")
    open_ports: list[int] = Field(default_factory=list, description="Open network ports")
    listening_services: list[str] = Field(default_factory=list, description="Services listening on network")
    security_updates_count: int | None = Field(default=None, description="Number of pending security updates")


class DiscoveryMetadata(BaseModel):
    """Metadata about the discovery process."""

    method: DiscoveryMethod = Field(default=DiscoveryMethod.MOCK, description="Discovery method used")
    source: DataSource = Field(default=DataSource.HEURISTIC_INFERENCE, description="Specific data source")
    collected_at: datetime = Field(default_factory=datetime.now, description="When data was collected")
    collection_duration_ms: float = Field(default=0.0, description="Duration of collection in ms")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH, description="Data confidence level")
    host: str = Field(default="", description="Host that was discovered")
    warnings: list[str] = Field(default_factory=list, description="Warnings during collection")
    errors: list[str] = Field(default_factory=list, description="Errors during collection")
    data_size_bytes: int | None = Field(default=None, description="Size of raw data collected")


class UnifiedDiscoveryModel(BaseModel):
    """Unified model combining all discovery data."""

    hardware: HardwareSpec = Field(default_factory=HardwareSpec, description="Hardware information")
    software: SoftwareEnvironment = Field(default_factory=SoftwareEnvironment, description="Software information")
    security: SecurityAssessment = Field(default_factory=SecurityAssessment, description="Security assessment")
    metadata: DiscoveryMetadata = Field(default_factory=DiscoveryMetadata, description="Discovery metadata")
    raw_facts: dict[str, Any] = Field(default_factory=dict, description="Raw discovery facts")


class DiscoveryResult(BaseModel):
    """Complete result of a discovery operation."""

    hosts: dict[str, UnifiedDiscoveryModel] = Field(
        default_factory=dict, description="Discovered hosts keyed by hostname"
    )
    total_hosts: int = Field(default=0, ge=0, description="Total number of hosts discovered")
    successful_hosts: int = Field(default=0, ge=0, description="Number of successful discoveries")
    failed_hosts: int = Field(default=0, ge=0, description="Number of failed discoveries")
    total_duration_ms: float = Field(default=0.0, description="Total discovery duration")
    errors: dict[str, list[str]] = Field(default_factory=dict, description="Errors per host")
