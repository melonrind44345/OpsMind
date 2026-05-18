"""Software data collector - supplementary software detection."""

import os
import subprocess
from typing import Dict, List, Optional

from opsmind.schemas.discovery import ServiceInfo, SoftwareEnvironment, SoftwarePackage


class SoftwareCollector:
    """Supplementary software data collection beyond Ansible facts."""

    @staticmethod
    def detect_container_runtime() -> Optional[str]:
        """Detect available container runtimes."""
        runtimes = ["docker", "podman", "containerd", "nerdctl"]
        for runtime in runtimes:
            try:
                result = subprocess.run(
                    [runtime, "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return runtime
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None

    @staticmethod
    def detect_orchestrators() -> List[str]:
        """Detect container orchestrators."""
        found: List[str] = []
        try:
            result = subprocess.run(
                ["kubectl", "version", "--short"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                found.append("kubernetes")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return found

    @staticmethod
    def check_docker_compose() -> bool:
        """Check if docker-compose is available."""
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        try:
            result = subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def detect_java_version() -> Optional[str]:
        """Detect installed Java version."""
        for java_cmd, flag in [("java", "-version"), ("java11", "-version"), ("java17", "-version")]:
            try:
                result = subprocess.run(
                    [java_cmd, flag],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    for line in (result.stderr or "").splitlines():
                        if "version" in line:
                            return line.strip()
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None

    @staticmethod
    def detect_python_version() -> Optional[str]:
        """Detect installed Python versions."""
        for py_cmd in ["python3", "python"]:
            try:
                result = subprocess.run(
                    [py_cmd, "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return result.stdout.strip() or result.stderr.strip()
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None

    @staticmethod
    def detect_node_version() -> Optional[str]:
        """Detect installed Node.js version."""
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    @staticmethod
    def enhance_service_status(env: SoftwareEnvironment) -> SoftwareEnvironment:
        """Enhance service information with additional detail."""
        for service in env.services:
            if service.state == "running":
                try:
                    pid_file = f"/var/run/{service.name}.pid"
                    if os.path.exists(pid_file):
                        with open(pid_file) as f:
                            pid_str = f.read().strip()
                            if pid_str.isdigit():
                                service.pid = int(pid_str)
                except (OSError, ValueError):
                    pass
        return env
