"""Security data collector - supplementary security detection."""

import os
import subprocess


class SecurityCollector:
    """Supplementary security data collection beyond Ansible facts."""

    @staticmethod
    def check_open_ports() -> list[int]:
        """Detect listening TCP ports."""
        open_ports: list[int] = []
        try:
            if os.path.exists("/usr/sbin/ss"):
                result = subprocess.run(
                    ["ss", "-tlnp"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 4:
                        addr_port = parts[3]
                        if ":" in addr_port:
                            port_str = addr_port.rsplit(":", 1)[-1]
                            if port_str.isdigit():
                                open_ports.append(int(port_str))
            elif os.path.exists("/bin/netstat"):
                result = subprocess.run(
                    ["netstat", "-tlnp"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 4:
                        addr_port = parts[3]
                        if ":" in addr_port:
                            port_str = addr_port.rsplit(":", 1)[-1]
                            if port_str.isdigit():
                                open_ports.append(int(port_str))
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass
        return sorted(set(open_ports))

    @staticmethod
    def check_ssh_security() -> dict[str, bool]:
        """Check SSH security configuration."""
        results = {
            "root_login_disabled": False,
            "password_auth_disabled": False,
            "protocol_2_only": False,
        }
        try:
            if os.path.exists("/etc/ssh/sshd_config"):
                with open("/etc/ssh/sshd_config") as f:
                    config = f.read().lower()
                results["root_login_disabled"] = "permitrootlogin no" in config
                results["password_auth_disabled"] = "passwordauthentication no" in config
                results["protocol_2_only"] = "protocol 2" in config
        except OSError:
            pass
        return results

    @staticmethod
    def check_pending_security_updates() -> int | None:
        """Count pending security updates."""
        try:
            if os.path.exists("/usr/bin/apt"):
                result = subprocess.run(
                    ["apt", "list", "--upgradable"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                lines = [line for line in result.stdout.splitlines() if "-security" in line]
                return len(lines)
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return None
