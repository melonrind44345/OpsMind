"""Mock discovery engine for demonstration and testing.

Generates realistic system data for demo scenarios when
no real hosts are available.
"""

import time
from typing import Any

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
    NetworkInterface,
    SecurityAssessment,
    ServiceInfo,
    SoftwareEnvironment,
    SoftwarePackage,
    UnifiedDiscoveryModel,
)


class MockDiscoveryEngine(BaseDiscoveryEngine):
    """Mock engine that generates realistic demo data."""

    MOCK_PROFILES = {
        "legacy-centos": {
            "hostname": "legacy-app-01",
            "platform": "Linux",
            "os_name": "CentOS",
            "os_version": "6.10",
            "os_family": "RedHat",
            "kernel": "2.6.32-754.el6.x86_64",
            "cpu_model": "Intel(R) Xeon(R) CPU E5-2680 v3 @ 2.50GHz",
            "cpu_cores": 4,
            "cpu_threads": 8,
            "memory_total_gb": 16.0,
            "memory_available_gb": 2.5,
            "disks": [
                {
                    "device": "/dev/sda1",
                    "mount": "/",
                    "fstype": "ext4",
                    "total": 100.0,
                    "used": 85.0,
                },
                {
                    "device": "/dev/sdb1",
                    "mount": "/data",
                    "fstype": "xfs",
                    "total": 500.0,
                    "used": 420.0,
                },
            ],
            "packages_count": 450,
            "services": [
                {"name": "httpd", "state": "running", "enabled": True},
                {"name": "mysqld", "state": "running", "enabled": True},
                {"name": "crond", "state": "running", "enabled": True},
                {"name": "network", "state": "running", "enabled": True},
                {"name": "iptables", "state": "stopped", "enabled": False},
            ],
            "zombie_services": ["sendmail", "rpcbind"],
            "open_ports": [22, 80, 443, 3306],
            "firewall_active": False,
            "selinux": "disabled",
            "os_uptodate": False,
            "security_updates": 47,
        },
        "modern-ubuntu": {
            "hostname": "modern-srv-01",
            "platform": "Linux",
            "os_name": "Ubuntu",
            "os_version": "22.04.3",
            "os_family": "Debian",
            "kernel": "5.15.0-91-generic",
            "cpu_model": "AMD EPYC 7763 64-Core Processor",
            "cpu_cores": 8,
            "cpu_threads": 16,
            "memory_total_gb": 64.0,
            "memory_available_gb": 32.0,
            "disks": [
                {
                    "device": "/dev/nvme0n1p2",
                    "mount": "/",
                    "fstype": "ext4",
                    "total": 200.0,
                    "used": 45.0,
                },
                {
                    "device": "/dev/nvme1n1",
                    "mount": "/data",
                    "fstype": "xfs",
                    "total": 1000.0,
                    "used": 200.0,
                },
            ],
            "packages_count": 680,
            "services": [
                {"name": "nginx", "state": "running", "enabled": True},
                {"name": "postgresql", "state": "running", "enabled": True},
                {"name": "redis-server", "state": "running", "enabled": True},
                {"name": "docker", "state": "running", "enabled": True},
                {"name": "ufw", "state": "active", "enabled": True},
            ],
            "open_ports": [22, 80, 443, 5432, 6379],
            "firewall_active": True,
            "selinux": "enforcing",
            "os_uptodate": True,
            "security_updates": 3,
        },
        "windows-server": {
            "hostname": "WIN-SRV-01",
            "platform": "Windows",
            "os_name": "Windows Server",
            "os_version": "2019",
            "os_family": "Windows",
            "kernel": "10.0.17763",
            "cpu_model": "Intel(R) Xeon(R) Gold 6248 CPU @ 2.50GHz",
            "cpu_cores": 8,
            "cpu_threads": 16,
            "memory_total_gb": 32.0,
            "memory_available_gb": 8.0,
            "disks": [
                {"device": "C:", "mount": "C:\\", "fstype": "NTFS", "total": 250.0, "used": 200.0},
                {"device": "D:", "mount": "D:\\", "fstype": "NTFS", "total": 1000.0, "used": 600.0},
            ],
            "packages_count": 320,
            "services": [
                {"name": "IIS", "state": "running", "enabled": True},
                {"name": "MSSQLSERVER", "state": "running", "enabled": True},
                {"name": "Windows Update", "state": "stopped", "enabled": True},
            ],
            "open_ports": [80, 443, 1433, 3389],
            "firewall_active": True,
            "os_uptodate": False,
            "security_updates": 23,
        },
    }

    def __init__(self, profile: str | None = None) -> None:
        self.profile = profile

    @property
    def method(self) -> DiscoveryMethod:
        return DiscoveryMethod.MOCK

    @property
    def is_available(self) -> bool:
        return True

    def discover_host(self, host: str) -> DiscoveryResult:
        """Generate mock data for the given host.

        Args:
            host: Hostname or 'legacy-centos', 'modern-ubuntu', 'windows-server'

        Returns:
            Mock discovery result
        """
        start_time = time.time()

        profile = self._select_profile(host)
        unified = self._build_unified(profile)

        duration = (time.time() - start_time) * 1000
        unified.metadata = self._create_metadata(
            host=profile["hostname"],
            source=DataSource.MOCK_DATA.value,
            duration_ms=duration,
        )
        unified.metadata.confidence = ConfidenceLevel.LOW
        unified.metadata.warnings = ["Mock data - not from real system discovery"]

        result = DiscoveryResult(
            hosts={profile["hostname"]: unified},
            total_hosts=1,
            successful_hosts=1,
            total_duration_ms=duration,
        )
        return result

    def discover_group(self, hosts: list[str], parallel: bool = True) -> DiscoveryResult:
        """Generate mock data for multiple hosts."""
        start_time = time.time()

        result = DiscoveryResult()
        for host in hosts:
            profile = self._select_profile(host)
            unified = self._build_unified(profile)
            duration = (time.time() - start_time) * 1000 / len(hosts)
            unified.metadata = self._create_metadata(
                host=profile["hostname"],
                source=DataSource.MOCK_DATA.value,
                duration_ms=duration,
            )
            unified.metadata.confidence = ConfidenceLevel.LOW
            unified.metadata.warnings = ["Mock data - not from real system discovery"]
            result.hosts[profile["hostname"]] = unified

        result.total_hosts = len(hosts)
        result.successful_hosts = len(hosts)
        result.total_duration_ms = (time.time() - start_time) * 1000
        return result

    def _select_profile(self, host: str) -> dict[str, Any]:
        """Select the appropriate mock profile."""
        if host in self.MOCK_PROFILES:
            return self.MOCK_PROFILES[host]
        if host and host != "localhost":
            return self.MOCK_PROFILES["legacy-centos"]
        return self.MOCK_PROFILES["legacy-centos"]

    def _build_unified(self, profile: dict[str, Any]) -> UnifiedDiscoveryModel:
        """Build UnifiedDiscoveryModel from profile data."""
        cpu = CPUInfo(
            model=profile.get("cpu_model", "Unknown"),
            architecture="x86_64",
            cores=profile.get("cpu_cores", 2),
            threads=profile.get("cpu_threads", 4),
        )

        memory = MemoryInfo(
            total_gb=profile.get("memory_total_gb", 8.0),
            available_gb=profile.get("memory_available_gb", 2.0),
            swap_total_gb=2.0,
            swap_available_gb=0.5,
        )

        disks = []
        for disk in profile.get("disks", []):
            disks.append(
                DiskInfo(
                    device=disk["device"],
                    mount_point=disk["mount"],
                    filesystem=disk["fstype"],
                    total_gb=disk["total"],
                    used_gb=disk["used"],
                    available_gb=disk["total"] - disk["used"],
                    is_ssd="nvme" in disk["device"],
                )
            )

        net_ifaces = [
            NetworkInterface(
                name="eth0",
                mac_address="00:1a:2b:3c:4d:5e",
                ipv4_addresses=["10.0.0.100"],
                is_up=True,
            ),
        ]

        hardware = HardwareSpec(
            hostname=profile.get("hostname", "unknown"),
            platform=profile.get("platform", "Linux"),
            cpu=cpu,
            memory=memory,
            disks=disks,
            network_interfaces=net_ifaces,
            uptime_seconds=86400 * 120,
        )

        packages = []
        for i in range(min(profile.get("packages_count", 100), 100)):
            packages.append(
                SoftwarePackage(
                    name=f"pkg-{i}",
                    version=f"{i % 10}.{i % 5}.{i % 3}",
                    architecture="x86_64",
                )
            )

        services = []
        for svc in profile.get("services", []):
            services.append(
                ServiceInfo(
                    name=svc["name"],
                    state=svc["state"],
                    enabled=svc["enabled"],
                    pid=1000 + hash(svc["name"]) % 50000 if svc["state"] == "running" else None,
                )
            )

        software = SoftwareEnvironment(
            os_name=profile.get("os_name", "Linux"),
            os_version=profile.get("os_version", ""),
            os_family=profile.get("os_family", "Linux"),
            kernel=profile.get("kernel", ""),
            hostname=profile.get("hostname", "unknown"),
            packages=packages,
            services=services,
            selinux_enabled=profile.get("selinux") == "enforcing",
            firewall_enabled=profile.get("firewall_active", False),
        )

        security = SecurityAssessment(
            os_uptodate=profile.get("os_uptodate", False),
            firewall_active=profile.get("firewall_active", False),
            selinux_enforcing=profile.get("selinux") == "enforcing",
            ssh_config_secure=False,
            open_ports=profile.get("open_ports", [22, 80]),
            security_updates_count=profile.get("security_updates", 0),
        )

        return UnifiedDiscoveryModel(
            hardware=hardware,
            software=software,
            security=security,
        )
