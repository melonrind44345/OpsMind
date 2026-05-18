"""Native discovery engine - local system detection without Ansible.

Fallback engine that uses psutil and system commands to collect
system facts when Ansible is not available.
"""

import os
import platform
import subprocess
import time
from typing import Any, Dict, List, Optional

from opsmind.core.events import EventBus, EventType
from opsmind.discovery.engines.base import BaseDiscoveryEngine
from opsmind.schemas.discovery import (
    CPUInfo,
    ConfidenceLevel,
    DataSource,
    DiscoveryMethod,
    DiscoveryResult,
    DiskInfo,
    HardwareSpec,
    MemoryInfo,
    NetworkInterface,
    SecurityAssessment,
    SoftwareEnvironment,
    SoftwarePackage,
    UnifiedDiscoveryModel,
)


class NativeDiscoveryEngine(BaseDiscoveryEngine):
    """Discovery engine using Python-native methods (psutil, platform, system commands)."""

    def __init__(self) -> None:
        self.event_bus = EventBus()

    @property
    def method(self) -> DiscoveryMethod:
        return DiscoveryMethod.NATIVE

    @property
    def is_available(self) -> bool:
        """Native engine is always available (uses Python stdlib + psutil)."""
        try:
            import psutil  # noqa: F401
            return True
        except ImportError:
            return False

    def discover_host(self, host: str) -> DiscoveryResult:
        """Discover local system using native methods.

        Args:
            host: Must be 'localhost' for native engine

        Returns:
            Discovery result with locally collected data
        """
        import psutil

        start_time = time.time()

        if host != "localhost":
            self.event_bus.emit_simple(EventType.WARNING, {
                "message": f"Native engine can only discover localhost, not '{host}'",
            })
            return self._discover_localhost()

        # CPU info
        cpu_info = CPUInfo(
            model=platform.processor() or "Unknown",
            architecture=platform.machine(),
            cores=psutil.cpu_count(logical=False) or 0,
            threads=psutil.cpu_count(logical=True) or 0,
        )

        # Memory info
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        memory_info = MemoryInfo(
            total_gb=round(mem.total / (1024 ** 3), 2),
            available_gb=round(mem.available / (1024 ** 3), 2),
            swap_total_gb=round(swap.total / (1024 ** 3), 2),
            swap_available_gb=round(swap.free / (1024 ** 3), 2),
        )

        # Disk info
        disks: List[DiskInfo] = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append(DiskInfo(
                    device=part.device,
                    mount_point=part.mountpoint,
                    filesystem=part.fstype,
                    total_gb=round(usage.total / (1024 ** 3), 2),
                    used_gb=round(usage.used / (1024 ** 3), 2),
                    available_gb=round(usage.free / (1024 ** 3), 2),
                    mount_options=part.opts.split(",") if part.opts else [],
                ))
            except PermissionError:
                continue

        # Network info
        net_ifaces: List[NetworkInterface] = []
        net_addrs = psutil.net_if_addrs()
        net_stats = psutil.net_if_stats()

        for name, addrs in net_addrs.items():
            ipv4: List[str] = []
            ipv6: List[str] = []
            mac = ""

            for addr in addrs:
                if addr.family == 2:  # AF_INET
                    ipv4.append(addr.address)
                elif addr.family == 23:  # AF_INET6
                    ipv6.append(addr.address)
                elif addr.family == 17:  # AF_PACKET
                    mac = addr.address

            stats = net_stats.get(name)
            net_ifaces.append(NetworkInterface(
                name=name,
                mac_address=mac,
                ipv4_addresses=ipv4,
                ipv6_addresses=ipv6,
                is_up=stats.isup if stats else True,
            ))

        hardware = HardwareSpec(
            hostname=platform.node(),
            platform=platform.system(),
            cpu=cpu_info,
            memory=memory_info,
            disks=disks,
            network_interfaces=net_ifaces,
            uptime_seconds=int(time.time() - psutil.boot_time()),
        )

        # Software info
        packages = self._collect_packages()
        software = SoftwareEnvironment(
            os_name=platform.system(),
            os_version=platform.version(),
            os_family=self._detect_os_family(),
            kernel=platform.release(),
            hostname=platform.node(),
            packages=packages,
        )

        # Security assessment
        security = SecurityAssessment(
            firewall_active=self._check_firewall(),
        )

        duration = (time.time() - start_time) * 1000
        unified = UnifiedDiscoveryModel(
            hardware=hardware,
            software=software,
            security=security,
            metadata=self._create_metadata(
                host="localhost",
                source=DataSource.NATIVE_DETECTION.value,
                duration_ms=duration,
            ),
        )

        result = DiscoveryResult(
            hosts={"localhost": unified},
            total_hosts=1,
            successful_hosts=1,
            total_duration_ms=duration,
        )
        return result

    def discover_group(self, hosts: List[str], parallel: bool = True) -> DiscoveryResult:
        """Native engine can only discover localhost."""
        results = DiscoveryResult()
        for host in hosts:
            if host == "localhost":
                host_result = self.discover_host(host)
                results.hosts.update(host_result.hosts)
                results.successful_hosts += 1
            else:
                results.failed_hosts += 1
                results.errors[host] = ["Native engine does not support remote hosts"]
        results.total_hosts = len(hosts)
        return results

    def _discover_localhost(self) -> DiscoveryResult:
        """Internal localhost discovery."""
        return self.discover_host("localhost")

    def _collect_packages(self) -> List[SoftwarePackage]:
        """Collect installed packages using system package manager."""
        packages: List[SoftwarePackage] = []

        if platform.system() != "Linux":
            return packages

        try:
            if os.path.exists("/usr/bin/dpkg"):
                result = subprocess.run(
                    ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split("\n")[:200]:  # Limit to 200 packages
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            name = parts[0]
                            version = parts[1] if len(parts) > 1 else ""
                            arch = parts[2] if len(parts) > 2 else ""
                            packages.append(SoftwarePackage(
                                name=name,
                                version=version,
                                architecture=arch,
                            ))
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass

        return packages

    def _detect_os_family(self) -> str:
        """Detect OS family."""
        system = platform.system().lower()
        if system == "linux":
            try:
                if os.path.exists("/etc/redhat-release"):
                    return "RedHat"
                if os.path.exists("/etc/debian_version"):
                    return "Debian"
                if os.path.exists("/etc/alpine-release"):
                    return "Alpine"
                return "Linux"
            except Exception:
                return "Linux"
        return system.capitalize()

    def _check_firewall(self) -> bool:
        """Check if firewall is active."""
        try:
            if os.path.exists("/usr/sbin/ufw"):
                result = subprocess.run(
                    ["ufw", "status"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return "active" in result.stdout.lower()
            return False
        except Exception:
            return False
