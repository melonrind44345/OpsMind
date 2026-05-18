"""Ansible utility functions."""

import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional


def check_ansible_available() -> bool:
    """Check if ansible is installed and available on PATH."""
    try:
        result = subprocess.run(
            ["ansible", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


def get_ansible_version() -> Optional[str]:
    """Get installed Ansible version string."""
    try:
        result = subprocess.run(
            ["ansible", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                return line.strip()
        return None
    except Exception:
        return None


def check_ansible_runner() -> bool:
    """Check if ansible-runner Python package is available."""
    try:
        import ansible_runner  # noqa: F401
        return True
    except ImportError:
        return False


def find_inventory_files(base_path: Optional[str] = None) -> List[str]:
    """Find Ansible inventory files in standard locations."""
    search_paths = []

    if base_path:
        search_paths.append(os.path.join(base_path, "ansible", "inventories"))
        search_paths.append(os.path.join(base_path, "inventory"))

    home = os.path.expanduser("~")
    search_paths.extend([
        os.path.join(home, "opsmind", "ansible", "inventories"),
        os.path.join(home, "opsmind", "inventory"),
        "/etc/ansible/hosts",
    ])

    inventories: List[str] = []
    for path in search_paths:
        if os.path.isfile(path):
            inventories.append(path)
        elif os.path.isdir(path):
            for f in sorted(os.listdir(path)):
                if f.endswith((".yml", ".yaml", ".ini", ".hosts")):
                    inventories.append(os.path.join(path, f))

    return inventories


def validate_ssh_connectivity(
    host: str,
    user: Optional[str] = None,
    key_file: Optional[str] = None,
    timeout: int = 10,
) -> bool:
    """Validate SSH connectivity to a remote host."""
    cmd = ["ssh"]

    if user:
        cmd.extend(["-l", user])
    if key_file:
        cmd.extend(["-i", key_file])

    cmd.extend(["-o", "StrictHostKeyChecking=no"])
    cmd.extend(["-o", "BatchMode=yes"])
    cmd.extend(["-o", f"ConnectTimeout={timeout}"])
    cmd.append(host)

    try:
        result = subprocess.run(
            cmd + ["exit"],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


def create_dynamic_inventory(hosts: List[str]) -> str:
    """Create a dynamic inventory string for the given hosts."""
    import tempfile

    lines = ["---", "all:", "  hosts:"]
    for host in hosts:
        lines.append(f"    {host}:")
        lines.append(f"      ansible_host: {host}")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", prefix="opsmind_inventory_", delete=False
    ) as f:
        f.write("\n".join(lines))
        return f.name


def get_playbook_path(name: str) -> Optional[str]:
    """Get path to a bundled playbook."""
    search_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "ansible", "playbooks"),
        os.path.join(os.getcwd(), "ansible", "playbooks"),
        os.path.join(os.path.expanduser("~"), ".opsmind", "playbooks"),
    ]

    for base in search_paths:
        path = os.path.join(base, f"{name}.yml")
        if os.path.exists(path):
            return os.path.abspath(path)

    return None
