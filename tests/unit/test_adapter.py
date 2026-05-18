"""Unit tests for Ansible fact adapter."""

import json
from pathlib import Path

import pytest

from opsmind.discovery.adapters.ansible_adapter import AnsibleFactAdapter


@pytest.fixture
def sample_facts() -> dict:
    """Load sample Ansible facts from fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "ansible_facts.json"
    with open(fixture_path) as f:
        return json.load(f)


class TestAnsibleFactAdapter:
    """Tests for AnsibleFactAdapter."""

    def setup_method(self):
        self.adapter = AnsibleFactAdapter()

    def test_to_unified_model(self, sample_facts):
        model = self.adapter.to_unified_model(sample_facts)
        assert model is not None
        assert model.hardware.hostname == "test-server-01"
        assert model.software.os_name == "CentOS"
        assert model.software.os_version == "7.9"
        assert model.software.kernel == "3.10.0-1160.el7.x86_64"

    def test_hardware_conversion(self, sample_facts):
        model = self.adapter.to_unified_model(sample_facts)
        hw = model.hardware

        # CPU
        assert hw.cpu.model == "Intel(R) Xeon(R) CPU E5-2680 v3 @ 2.50GHz"
        assert hw.cpu.cores == 4
        assert hw.cpu.threads == 8
        assert hw.cpu.architecture == "x86_64"

        # Memory
        assert hw.memory.total_gb == 16.0
        assert hw.memory.available_gb == 2.0
        assert hw.memory.swap_total_gb == 4.0

        # Disks
        assert len(hw.disks) == 2
        assert hw.disks[0].device == "/dev/sda1"
        assert hw.disks[0].mount_point == "/"
        assert hw.disks[0].total_gb > 0

        # Network
        assert len(hw.network_interfaces) >= 2

        # System info
        assert hw.system_vendor == "Dell Inc."
        assert hw.system_model == "PowerEdge R730"

    def test_software_conversion(self, sample_facts):
        model = self.adapter.to_unified_model(sample_facts)
        sw = model.software

        assert sw.os_name == "CentOS"
        assert sw.os_version == "7.9"
        assert sw.os_family == "RedHat"
        assert sw.hostname == "test-server-01"

        # Services
        assert len(sw.services) > 0
        httpd = next((s for s in sw.services if s.name == "httpd"), None)
        assert httpd is not None
        assert httpd.state == "running"
        assert httpd.enabled is True

        # Packages
        assert len(sw.packages) > 0

    def test_security_conversion(self, sample_facts):
        model = self.adapter.to_unified_model(sample_facts)
        sec = model.security

        assert sec.selinux_enforcing is False

    def test_empty_facts(self):
        model = self.adapter.to_unified_model({})
        assert model is not None
        assert model.hardware.hostname == ""

    def test_partial_facts(self):
        facts = {"ansible_hostname": "test-box", "ansible_system": "Linux"}
        model = self.adapter.to_unified_model(facts)
        assert model.hardware.hostname == "test-box"
        assert model.hardware.platform == "Linux"
