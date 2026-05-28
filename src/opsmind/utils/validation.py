"""Input validation utilities."""

import ipaddress
import re
from typing import Any

ValidationResult = tuple[bool, str | None]


def validate_hostname(hostname: str) -> ValidationResult:
    """Validate a hostname string."""
    if not hostname or not hostname.strip():
        return False, "Hostname cannot be empty"

    if len(hostname) > 255:
        return False, "Hostname too long (max 255 characters)"

    if hostname == "localhost":
        return True, None

    # IP address check
    try:
        ipaddress.ip_address(hostname)
        return True, None
    except ValueError:
        pass

    # Hostname pattern
    pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"
    if re.match(pattern, hostname):
        return True, None

    return False, f"Invalid hostname format: {hostname}"


def validate_port(port: int) -> ValidationResult:
    """Validate a port number."""
    if not isinstance(port, int):
        return False, "Port must be an integer"
    if port < 1 or port > 65535:
        return False, f"Port {port} out of range (1-65535)"
    return True, None


def validate_ssh_key(key_path: str) -> ValidationResult:
    """Validate SSH key file path."""
    import os

    if not key_path:
        return False, "SSH key path cannot be empty"

    if not os.path.exists(key_path):
        return False, f"SSH key not found: {key_path}"

    if not os.path.isfile(key_path):
        return False, f"SSH key path is not a file: {key_path}"

    mode = os.stat(key_path).st_mode
    if mode & 0o077:  # Check if key has group/others permissions
        return True, "SSH key has broad permissions (should be 600)"

    return True, None


def validate_inventory_path(path: str) -> ValidationResult:
    """Validate inventory file path."""
    import os

    if not path:
        return True, None  # Optional field

    if not os.path.exists(path):
        return False, f"Inventory not found: {path}"

    return True, None


def validate_discovery_method(method: str) -> ValidationResult:
    """Validate discovery method."""
    valid_methods = {"ansible", "native", "mock", "auto"}
    if method.lower() not in valid_methods:
        return False, f"Invalid method '{method}'. Valid: {', '.join(sorted(valid_methods))}"
    return True, None


def validate_report_format(fmt: str) -> ValidationResult:
    """Validate report format."""
    valid_formats = {"markdown", "json", "html"}
    if fmt.lower() not in valid_formats:
        return False, f"Invalid format '{fmt}'. Valid: {', '.join(sorted(valid_formats))}"
    return True, None


def validate_config(config: dict[str, Any]) -> list[str]:
    """Validate tool configuration."""
    errors: list[str] = []

    if "discovery_method" in config:
        ok, msg = validate_discovery_method(config["discovery_method"])
        if not ok and msg:
            errors.append(msg)

    if "ansible_timeout" in config:
        timeout = config["ansible_timeout"]
        if not isinstance(timeout, int) or timeout < 1 or timeout > 300:
            errors.append(f"ansible_timeout must be 1-300, got {timeout}")

    if "max_retries" in config:
        retries = config["max_retries"]
        if not isinstance(retries, int) or retries < 0 or retries > 10:
            errors.append(f"max_retries must be 0-10, got {retries}")

    if "parallel_hosts" in config:
        parallel = config["parallel_hosts"]
        if not isinstance(parallel, int) or parallel < 1 or parallel > 100:
            errors.append(f"parallel_hosts must be 1-100, got {parallel}")

    return errors
