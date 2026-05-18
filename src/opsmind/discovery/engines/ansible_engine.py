"""Ansible-powered discovery engine.

Executes Ansible setup modules and custom playbooks to collect
system facts from local and remote hosts via SSH.
"""

import asyncio
import json
import os
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional

from opsmind.core.events import EventBus, EventType
from opsmind.core.exceptions import AnsibleError, AnsibleNotAvailableError, SSHConnectionError
from opsmind.discovery.adapters.ansible_adapter import AnsibleFactAdapter
from opsmind.discovery.engines.base import BaseDiscoveryEngine
from opsmind.schemas.discovery import (
    ConfidenceLevel,
    DataSource,
    DiscoveryMetadata,
    DiscoveryMethod,
    DiscoveryResult,
    UnifiedDiscoveryModel,
)


class AnsibleDiscoveryEngine(BaseDiscoveryEngine):
    """Discovery engine that uses Ansible to collect system facts."""

    def __init__(
        self,
        inventory_path: Optional[str] = None,
        ssh_config: Optional[Dict[str, Any]] = None,
        timeout: int = 10,
        max_retries: int = 2,
    ) -> None:
        self.inventory_path = inventory_path
        self.ssh_config = ssh_config or {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.event_bus = EventBus()
        self._available: Optional[bool] = None

    @property
    def method(self) -> DiscoveryMethod:
        return DiscoveryMethod.ANSIBLE

    @property
    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        self._available = self._check_ansible()
        return self._available

    def _check_ansible(self) -> bool:
        """Check if Ansible is installed and available."""
        try:
            import subprocess

            result = subprocess.run(
                ["ansible", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return False

    def _get_ansible_version(self) -> str:
        """Get installed Ansible version."""
        try:
            import subprocess

            result = subprocess.run(
                ["ansible", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "core" in line or "ansible" in line.lower():
                        return line.strip()
            return "unknown"
        except Exception:
            return "unknown"

    def discover_host(self, host: str) -> DiscoveryResult:
        """Discover a single host via Ansible.

        Args:
            host: Hostname or IP address

        Returns:
            Structured discovery result
        """
        if not self.is_available:
            raise AnsibleNotAvailableError(details={"host": host, "ansible_version": self._get_ansible_version()})

        if host == "localhost":
            return self._discover_localhost()

        return self._discover_remote(host)

    def discover_group(self, hosts: List[str], parallel: bool = True) -> DiscoveryResult:
        """Discover multiple hosts.

        Args:
            hosts: List of hostnames/IPs
            parallel: Whether to discover in parallel

        Returns:
            Combined discovery result
        """
        if not hosts:
            return DiscoveryResult()

        if parallel and len(hosts) > 1:
            return self._discover_parallel(hosts)

        result = DiscoveryResult()
        for host in hosts:
            try:
                host_result = self.discover_host(host)
                result.hosts.update(host_result.hosts)
                result.successful_hosts += 1
            except Exception as exc:
                result.failed_hosts += 1
                result.errors[host] = [str(exc)]
        result.total_hosts = len(hosts)
        return result

    def _discover_localhost(self) -> DiscoveryResult:
        """Discover localhost using Ansible local connection."""
        start_time = time.time()

        facts = self._run_ansible_setup("localhost", connection="local")

        duration = (time.time() - start_time) * 1000

        adapter = AnsibleFactAdapter()
        unified = adapter.to_unified_model(facts)
        unified.metadata = DiscoveryMetadata(
            method=DiscoveryMethod.ANSIBLE,
            source=DataSource.ANSIBLE_SETUP,
            collected_at=__import__("datetime").datetime.now(),
            collection_duration_ms=duration,
            confidence=ConfidenceLevel.HIGH,
            host="localhost",
        )
        unified.raw_facts = facts

        result = DiscoveryResult(
            hosts={"localhost": unified},
            total_hosts=1,
            successful_hosts=1,
            total_duration_ms=duration,
        )
        return result

    def _discover_remote(self, host: str) -> DiscoveryResult:
        """Discover a remote host via SSH."""
        start_time = time.time()

        facts = self._run_ansible_setup(host, connection="ssh")

        duration = (time.time() - start_time) * 1000

        adapter = AnsibleFactAdapter()
        unified = adapter.to_unified_model(facts)
        unified.metadata = DiscoveryMetadata(
            method=DiscoveryMethod.ANSIBLE,
            source=DataSource.ANSIBLE_SETUP,
            collected_at=__import__("datetime").datetime.now(),
            collection_duration_ms=duration,
            confidence=ConfidenceLevel.HIGH,
            host=host,
        )
        unified.raw_facts = facts

        # Extract actual hostname from facts if available
        actual_hostname = facts.get("ansible_hostname", host)
        result = DiscoveryResult(
            hosts={actual_hostname: unified},
            total_hosts=1,
            successful_hosts=1,
            total_duration_ms=duration,
        )
        return result

    def _discover_parallel(self, hosts: List[str]) -> DiscoveryResult:
        """Discover multiple hosts in parallel using Ansible."""
        start_time = time.time()

        facts_list = self._run_ansible_setup_parallel(hosts)

        duration = (time.time() - start_time) * 1000

        adapter = AnsibleFactAdapter()
        result = DiscoveryResult()
        success = 0
        failed = 0

        for host, facts in zip(hosts, facts_list):
            if facts is None:
                failed += 1
                result.errors[host] = ["Discovery failed"]
                continue
            try:
                unified = adapter.to_unified_model(facts)
                unified.metadata = DiscoveryMetadata(
                    method=DiscoveryMethod.ANSIBLE,
                    source=DataSource.ANSIBLE_SETUP,
                    collected_at=__import__("datetime").datetime.now(),
                    collection_duration_ms=duration / len(hosts),
                    confidence=ConfidenceLevel.HIGH,
                    host=host,
                )
                unified.raw_facts = facts
                hostname = facts.get("ansible_hostname", host)
                result.hosts[hostname] = unified
                success += 1
            except Exception:
                failed += 1
                result.errors[host] = ["Data conversion failed"]

        result.total_hosts = len(hosts)
        result.successful_hosts = success
        result.failed_hosts = failed
        result.total_duration_ms = duration
        return result

    def _run_ansible_setup(self, host: str, connection: str = "ssh") -> Dict[str, Any]:
        """Execute ansible setup module on a single host.

        Args:
            host: Target host
            connection: Connection type (local, ssh)

        Returns:
            Ansible facts dictionary
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                return self._execute_setup(host, connection)
            except AnsibleError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    self.event_bus.emit_simple(EventType.ENGINE_RETRY, {
                        "host": host,
                        "attempt": attempt + 1,
                        "error": str(exc),
                    })
                    time.sleep(1 * (attempt + 1))
                else:
                    raise

        raise last_error or AnsibleError(f"Failed to discover {host}")

    def _execute_setup(self, host: str, connection: str) -> Dict[str, Any]:
        """Execute the actual ansible command."""
        import subprocess

        with tempfile.TemporaryDirectory(prefix="opsmind_") as tmpdir:
            inventory_content = self._build_inventory_content(host, connection)
            inventory_file = os.path.join(tmpdir, "inventory.yml")
            with open(inventory_file, "w") as f:
                f.write(inventory_content)

            playbook_content = self._build_playbook_content()
            playbook_file = os.path.join(tmpdir, "discover.yml")
            with open(playbook_file, "w") as f:
                f.write(playbook_content)

            output_file = os.path.join(tmpdir, "output.json")

            cmd = [
                "ansible-playbook",
                "-i", inventory_file,
                playbook_file,
                "-e", f"output_file={output_file}",
                "--timeout", str(self.timeout),
            ]

            if connection == "local":
                cmd.append("--connection=local")

            if self.ssh_config.get("user"):
                cmd.extend(["--user", self.ssh_config["user"]])
            if self.ssh_config.get("key_file"):
                cmd.extend(["--private-key", self.ssh_config["key_file"]])
            cmd.append(host)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 30,
            )

            if result.returncode != 0:
                stderr = result.stderr[:500]
                if "UNREACHABLE" in stderr:
                    raise SSHConnectionError(host, details={"stderr": stderr})
                raise AnsibleError(
                    f"Ansible execution failed for {host}: {stderr}",
                    details={"returncode": result.returncode, "stderr": stderr},
                )

            if os.path.exists(output_file):
                with open(output_file) as f:
                    raw_output = json.load(f)
            else:
                raw_output = self._parse_ansible_output(result.stdout)

            facts = self._extract_facts(raw_output, host)
            return facts

    def _build_inventory_content(self, host: str, connection: str) -> str:
        """Build Ansible inventory content for the target."""
        return f"""---
all:
  hosts:
    {host}:
      ansible_connection: {"local" if connection == "local" else "ssh"}
      ansible_host: {"127.0.0.1" if connection == "local" else host}
"""

    def _build_playbook_content(self) -> str:
        """Build the discovery playbook content."""
        return """---
- name: OpsMind System Discovery
  hosts: all
  gather_facts: yes
  gather_subset:
    - all
  tasks:
    - name: Collect discovery data
      ansible.builtin.setup:
        gather_subset: "all"
      register: setup_result

    - name: Save discovery data
      ansible.builtin.copy:
        content: "{{ ansible_facts | to_nice_json }}"
        dest: "{{ output_file }}"
      delegate_to: localhost
      run_once: yes
  environment:
    ANSIBLE_HOST_KEY_CHECKING: "False"
    ANSIBLE_TIMEOUT: "{{ lookup('env', 'ANSIBLE_TIMEOUT') | default('10', true) }}"
"""

    def _parse_ansible_output(self, stdout: str) -> Dict[str, Any]:
        """Parse ansible-playbook stdout to extract facts."""
        import re

        facts: Dict[str, Any] = {}
        in_facts = False
        json_buffer = ""

        for line in stdout.splitlines():
            if '"ansible_facts"' in line or "ansible_facts" in line:
                in_facts = True
            if in_facts:
                json_buffer += line + "\n"
                if line.strip().endswith("}"):
                    break

        if json_buffer:
            try:
                parsed = json.loads(json_buffer)
                if isinstance(parsed, dict) and "ansible_facts" in parsed:
                    facts = parsed["ansible_facts"]
            except (json.JSONDecodeError, KeyError):
                pass

        return facts

    def _extract_facts(self, raw_output: Dict[str, Any], host: str) -> Dict[str, Any]:
        """Extract and normalize Ansible facts from raw output."""
        facts: Dict[str, Any] = {}

        if isinstance(raw_output, dict):
            for key in list(raw_output.keys()):
                if key.startswith("ansible_"):
                    facts[key] = raw_output[key]

            if not facts:
                facts = {f"ansible_{k}": v for k, v in raw_output.items() if isinstance(v, (str, int, float, bool, list, dict))}

        if not facts:
            raise AnsibleError(f"No facts collected for {host}", details={"host": host})

        return facts

    def _run_ansible_setup_parallel(self, hosts: List[str]) -> List[Optional[Dict[str, Any]]]:
        """Run ansible setup for multiple hosts."""
        import subprocess

        with tempfile.TemporaryDirectory(prefix="opsmind_") as tmpdir:
            inventory_lines = ["all:", "  hosts:"]
            for host in hosts:
                inventory_lines.append(f"    {host}:")
                inventory_lines.append(f"      ansible_host: {host}")
                inventory_lines.append(f"      ansible_connection: ssh")

            inventory_file = os.path.join(tmpdir, "inventory.yml")
            with open(inventory_file, "w") as f:
                f.write("\n".join(inventory_lines))

            output_file = os.path.join(tmpdir, "output.json")

            cmd = [
                "ansible",
                "-i", inventory_file,
                "-m", "setup",
                "--tree", tmpdir,
                "--timeout", str(self.timeout),
            ]

            if self.ssh_config.get("user"):
                cmd.extend(["--user", self.ssh_config["user"]])
            if self.ssh_config.get("key_file"):
                cmd.extend(["--private-key", self.ssh_config["key_file"]])
            cmd.extend(hosts)

            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 30,
            )

            results: List[Optional[Dict[str, Any]]] = []
            for host in hosts:
                host_file = os.path.join(tmpdir, host)
                if os.path.exists(host_file):
                    try:
                        with open(host_file) as f:
                            data = json.load(f)
                        facts = data.get("ansible_facts", {})
                        results.append(facts)
                    except (json.JSONDecodeError, IOError):
                        results.append(None)
                else:
                    results.append(None)

            return results
