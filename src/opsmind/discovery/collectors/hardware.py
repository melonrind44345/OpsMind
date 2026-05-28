"""Hardware data collector - supplementary hardware detection."""

from opsmind.schemas.discovery import DiskInfo, HardwareSpec, MemoryInfo


class HardwareCollector:
    """Supplementary hardware data collection beyond Ansible facts."""

    @staticmethod
    def enhance_with_dmi(hardware: HardwareSpec) -> HardwareSpec:
        """Enhance hardware spec with DMI/BIOS information if available."""
        import subprocess

        try:
            if hardware.system_vendor is None or hardware.system_vendor == "":
                result = subprocess.run(
                    ["dmidecode", "-s", "system-manufacturer"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    hardware.system_vendor = result.stdout.strip()

            if hardware.system_model is None or hardware.system_model == "":
                result = subprocess.run(
                    ["dmidecode", "-s", "system-product-name"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    hardware.system_model = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass

        return hardware

    @staticmethod
    def estimate_memory_type(memory: MemoryInfo) -> str | None:
        """Estimate memory type based on total capacity and era."""
        if memory.total_gb <= 8:
            return "DDR3"
        elif memory.total_gb <= 32:
            return "DDR4"
        elif memory.total_gb > 32:
            return "DDR5"
        return None

    @staticmethod
    def estimate_disk_type(disk: DiskInfo) -> bool:
        """Estimate whether disk is SSD based on device name."""
        ssd_indicators = ["nvme", "ssd", "sd"]
        device_lower = disk.device.lower()
        return any(indicator in device_lower for indicator in ssd_indicators)
