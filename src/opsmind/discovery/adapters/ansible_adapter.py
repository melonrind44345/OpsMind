"""Ansible facts adapter - converts Ansible facts to unified data models.

Handles the mapping from Ansible's fact naming convention to OpsMind's
standardized data model with appropriate type conversions and validation.
"""

from typing import Any, overload

from opsmind.discovery.adapters.base_adapter import BaseAdapter
from opsmind.schemas.discovery import (
    CPUInfo,
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


class AnsibleFactAdapter(BaseAdapter):
    """Converts Ansible facts to UnifiedDiscoveryModel.

    Handles the mapping from Ansible's nested fact structure to
    OpsMind's standardized schema with type conversion and validation.
    """

    def to_unified_model(self, facts: dict[str, Any]) -> UnifiedDiscoveryModel:
        """Convert Ansible facts dictionary to unified model.

        Args:
            facts: Raw Ansible facts dictionary

        Returns:
            Standardized UnifiedDiscoveryModel
        """
        hardware = self._to_hardware(facts)
        software = self._to_software(facts)
        security = self._to_security(facts)

        return UnifiedDiscoveryModel(
            hardware=hardware,
            software=software,
            security=security,
        )

    def _to_hardware(self, facts: dict[str, Any]) -> HardwareSpec:
        """Extract hardware information from Ansible facts."""
        hostname = self._safe_get(facts, "ansible_hostname", "")

        cpu = self._to_cpu(facts)
        memory = self._to_memory(facts)
        disks = self._to_disks(facts)
        net_ifaces = self._to_network(facts)

        vendor = self._safe_get(facts, "ansible_system_vendor")
        model = self._safe_get(facts, "ansible_product_name")
        bios = self._safe_get(facts, "ansible_bios_version")

        uptime_seconds = self._to_uptime(facts)

        return HardwareSpec(
            hostname=hostname,
            platform=self._safe_get(facts, "ansible_system", ""),
            cpu=cpu,
            memory=memory,
            disks=disks,
            network_interfaces=net_ifaces,
            system_vendor=vendor,
            system_model=model,
            bios_version=bios,
            uptime_seconds=uptime_seconds,
        )

    def _to_cpu(self, facts: dict[str, Any]) -> CPUInfo:
        """Extract CPU information."""
        processor = facts.get("ansible_processor", [])
        cpu_model = ""
        if isinstance(processor, list):
            cpu_model = processor[-1] if processor else ""
        elif isinstance(processor, str):
            cpu_model = processor

        cores = self._safe_int(facts, "ansible_processor_cores", 0)
        threads = self._safe_int(facts, "ansible_processor_vcpus", 0)
        architecture = self._safe_get(facts, "ansible_architecture", "")

        freq_cur = self._safe_float(facts, "ansible_processor_frequency", None)
        cache = self._safe_int(facts, "ansible_processor_cache_size", None)

        flags = []
        if "ansible_processor_flags" in facts:
            flags_data = facts["ansible_processor_flags"]
            if isinstance(flags_data, list):
                flags = [str(f) for f in flags_data[:20]]

        return CPUInfo(
            model=cpu_model,
            architecture=architecture,
            cores=max(cores, 1),
            threads=max(threads, 1),
            frequency_mhz=freq_cur,
            cache_size_kb=cache,
            flags=flags,
        )

    def _to_memory(self, facts: dict[str, Any]) -> MemoryInfo:
        """Extract memory information."""
        mem_total_mb = self._safe_float(facts, "ansible_memtotal_mb", 0)
        mem_free_mb = self._safe_float(facts, "ansible_memfree_mb", 0)
        swap_total_mb = self._safe_float(facts, "ansible_swaptotal_mb", 0)
        swap_free_mb = self._safe_float(facts, "ansible_swapfree_mb", 0)

        return MemoryInfo(
            total_gb=round(mem_total_mb / 1024, 2),
            available_gb=round(mem_free_mb / 1024, 2),
            swap_total_gb=round(swap_total_mb / 1024, 2),
            swap_available_gb=round(swap_free_mb / 1024, 2),
        )

    def _to_disks(self, facts: dict[str, Any]) -> list[DiskInfo]:
        """Extract disk information."""
        disks: list[DiskInfo] = []
        mounts = facts.get("ansible_mounts", [])
        if not isinstance(mounts, list):
            return disks

        for mount in mounts:
            if not isinstance(mount, dict):
                continue
            try:
                total = self._safe_float(mount, "size_total", 0)
                used = self._safe_float(mount, "size_used", 0)
                available_explicit = self._safe_float(mount, "size_available", total - used)

                disks.append(
                    DiskInfo(
                        device=self._safe_get(mount, "device", ""),
                        mount_point=self._safe_get(mount, "mount", ""),
                        filesystem=self._safe_get(mount, "fstype", ""),
                        total_gb=round(total / (1024**3), 2) if total > 1e9 else round(total, 2),
                        used_gb=round(used / (1024**3), 2) if used > 1e9 else round(used, 2),
                        available_gb=round(available_explicit / (1024**3), 2)
                        if available_explicit > 1e9
                        else round(available_explicit, 2),
                        mount_options=self._safe_get(mount, "options", "").split(",")
                        if isinstance(self._safe_get(mount, "options", ""), str)
                        else [],
                    )
                )
            except (ValueError, TypeError):
                continue
        return disks

    def _to_network(self, facts: dict[str, Any]) -> list[NetworkInterface]:
        """Extract network interface information."""
        interfaces: list[NetworkInterface] = []
        ifaces = facts.get("ansible_interfaces", [])
        if not isinstance(ifaces, list):
            return interfaces

        for iface_name in ifaces:
            iface_key = f"ansible_{iface_name}"
            iface_data = facts.get(iface_key, {})

            if not isinstance(iface_data, dict):
                continue

            ipv4 = iface_data.get("ipv4", {}) or {}
            ipv6 = iface_data.get("ipv6", {}) or {}

            interfaces.append(
                NetworkInterface(
                    name=iface_name,
                    mac_address=self._safe_get(iface_data, "macaddress", ""),
                    ipv4_addresses=[ipv4.get("address", "")] if ipv4.get("address") else [],
                    ipv6_addresses=[ipv6.get("address", "")] if ipv6.get("address") else [],
                    speed_mbps=self._safe_int(iface_data, "speed", None),
                    is_up=self._safe_get(iface_data, "active", True),
                    is_virtual=self._safe_get(iface_data, "type", "") in ("bridge", "bond", "vlan", "dummy"),
                )
            )
        return interfaces

    def _to_software(self, facts: dict[str, Any]) -> SoftwareEnvironment:
        """Extract software environment information."""
        packages = self._to_packages(facts)
        services = self._to_services(facts)

        hostname = self._safe_get(facts, "ansible_hostname", "")
        distribution = self._safe_get(facts, "ansible_distribution", "")
        dist_version = self._safe_get(facts, "ansible_distribution_version", "")
        dist_family = self._safe_get(facts, "ansible_os_family", "")
        kernel = self._safe_get(facts, "ansible_kernel", "")

        selinux = facts.get("ansible_selinux", {}) or {}
        firewalld = facts.get("ansible_firewalld", {}) or {}

        return SoftwareEnvironment(
            os_name=str(distribution),
            os_version=str(dist_version),
            os_family=str(dist_family),
            kernel=str(kernel),
            hostname=str(hostname),
            packages=packages,
            services=services,
            selinux_enabled=bool(selinux.get("enabled")),
            firewall_enabled=bool(firewalld.get("status") == "running") if isinstance(firewalld, dict) else None,
        )

    def _to_packages(self, facts: dict[str, Any]) -> list[SoftwarePackage]:
        """Extract package information."""
        packages: list[SoftwarePackage] = []

        for pkg_key in ("ansible_packages", "packages"):
            pkg_data = facts.get(pkg_key, facts.get(pkg_key.replace("ansible_", "")))
            if isinstance(pkg_data, dict):
                for name, info_list in pkg_data.items():
                    if isinstance(info_list, list) and info_list:
                        info = info_list[0] if isinstance(info_list[0], dict) else {}
                        packages.append(
                            SoftwarePackage(
                                name=str(name),
                                version=str(info.get("version", "")),
                                architecture=str(info.get("arch", "")),
                                vendor=str(info.get("origin", "")) if info.get("origin") else None,
                            )
                        )
                    elif isinstance(info_list, dict):
                        packages.append(
                            SoftwarePackage(
                                name=str(name),
                                version=str(info_list.get("version", "")),
                                architecture=str(info_list.get("arch", "")),
                            )
                        )
            elif isinstance(pkg_data, list):
                for pkg in pkg_data:
                    if isinstance(pkg, dict):
                        packages.append(
                            SoftwarePackage(
                                name=str(pkg.get("name", "")),
                                version=str(pkg.get("version", "")),
                                architecture=str(pkg.get("arch", "")),
                            )
                        )
        return packages[:200]

    def _to_services(self, facts: dict[str, Any]) -> list[ServiceInfo]:
        """Extract service information."""
        services: list[ServiceInfo] = []
        svc_data = facts.get("ansible_services", {})
        if isinstance(svc_data, dict):
            for name, info in list(svc_data.items())[:100]:
                if isinstance(info, dict):
                    services.append(
                        ServiceInfo(
                            name=str(name),
                            state=str(info.get("state", "unknown")),
                            enabled=bool(info.get("enabled", False)),
                        )
                    )
                elif isinstance(info, str):
                    services.append(
                        ServiceInfo(
                            name=str(name),
                            state=info,
                            enabled=False,
                        )
                    )
        return services

    def _to_security(self, facts: dict[str, Any]) -> SecurityAssessment:
        """Extract security baseline information."""
        selinux = facts.get("ansible_selinux", {}) or {}
        firewalld = facts.get("ansible_firewalld", {}) or {}

        return SecurityAssessment(
            os_uptodate=self._safe_get(facts, "ansible_pkg_mgr", "") != "",
            firewall_active=bool(firewalld.get("status") == "running") if isinstance(firewalld, dict) else False,
            selinux_enforcing=bool(selinux.get("mode") == "enforcing") if isinstance(selinux, dict) else None,
            listening_services=[],
        )

    def _to_uptime(self, facts: dict[str, Any]) -> int | None:
        """Extract uptime in seconds."""
        boot_time = facts.get("ansible_date_time", {}).get("epoch", None)
        if boot_time:
            try:
                import time

                return int(time.time()) - int(boot_time)
            except (ValueError, TypeError):
                pass
        return None

    @staticmethod
    def _safe_get(data: dict[str, Any], key: str, default: Any = "") -> Any:
        """Safely get a value from a dictionary."""
        value = data.get(key, default)
        return value if value is not None else default

    @overload
    @staticmethod
    def _safe_int(data: dict[str, Any], key: str, default: int = 0) -> int: ...
    @overload
    @staticmethod
    def _safe_int(data: dict[str, Any], key: str, default: None) -> int | None: ...
    @staticmethod
    def _safe_int(data: dict[str, Any], key: str, default: int | None = 0) -> int | None:
        """Safely extract an integer value."""
        value = data.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @overload
    @staticmethod
    def _safe_float(data: dict[str, Any], key: str, default: float = 0.0) -> float: ...
    @overload
    @staticmethod
    def _safe_float(data: dict[str, Any], key: str, default: None) -> float | None: ...
    @staticmethod
    def _safe_float(data: dict[str, Any], key: str, default: float | None = 0.0) -> float | None:
        """Safely extract a float value."""
        value = data.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
