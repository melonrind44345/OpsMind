"""Unit tests for OpsMind engine components."""

import pytest

from opsmind.core.engine import OpsMindEngine
from opsmind.core.events import EventBus, EventType
from opsmind.core.exceptions import DiscoveryError


class TestOpsMindEngine:
    """Tests for the main OpsMind engine."""

    def setup_method(self):
        self.engine = OpsMindEngine()

    def test_engine_initialization(self):
        assert self.engine.config is not None
        assert self.engine.event_bus is not None

    def test_invalid_target(self):
        with pytest.raises(DiscoveryError):
            self.engine.discover("")

    def test_resolve_method_valid(self):
        method = self.engine._resolve_method("ansible")
        assert method.value == "ansible"

        method = self.engine._resolve_method("auto")
        assert method.value == "auto"

    def test_resolve_method_invalid(self):
        with pytest.raises(DiscoveryError):
            self.engine._resolve_method("invalid_method")

    def test_discover_mock(self):
        result = self.engine.discover("localhost", method="mock")
        assert result is not None
        assert result.total_hosts >= 1
        assert len(result.hosts) >= 1  # Mock engine may rename the host

    def test_discover_mock_legacy(self):
        result = self.engine.discover("legacy-centos", method="mock")
        assert result.total_hosts >= 1
        # The mock engine may rename the host
        assert len(result.hosts) > 0

    def test_discover_mock_modern(self):
        result = self.engine.discover("modern-ubuntu", method="mock")
        assert result.total_hosts >= 1
        assert len(result.hosts) > 0

    def test_assess_from_mock_discovery(self):
        disc = self.engine.discover("localhost", method="mock")
        results = self.engine.assess(disc)
        assert len(results) > 0
        for hostname, result in results.items():
            assert result.feasibility.overall_score >= 0
            assert result.feasibility.overall_score <= 100
            assert result.complexity.estimated_effort_days is not None
            assert result.migration_strategy.strategy_type != ""

    def test_pipeline_mock(self):
        result = self.engine.run_pipeline("localhost", method="mock")
        assert "discovery" in result
        assert "assessment" in result
        assert "report" in result
        assert len(result["assessment"]) > 0


class TestEventBus:
    """Tests for the event bus system."""

    def setup_method(self):
        EventBus().reset()
        self.bus = EventBus()

    def test_singleton(self):
        bus2 = EventBus()
        assert self.bus is bus2

    def test_subscribe_and_emit(self):
        received = []

        def handler(event):
            received.append(event)

        self.bus.subscribe(EventType.DISCOVERY_STARTED, handler)
        self.bus.emit_simple(EventType.DISCOVERY_STARTED, {"target": "localhost"})

        assert len(received) == 1
        assert received[0].data["target"] == "localhost"

    def test_unsubscribe(self):
        received = []

        def handler(event):
            received.append(event)

        self.bus.subscribe(EventType.DISCOVERY_COMPLETED, handler)
        self.bus.unsubscribe(EventType.DISCOVERY_COMPLETED, handler)
        self.bus.emit_simple(EventType.DISCOVERY_COMPLETED)

        assert len(received) == 0

    def test_history(self):
        self.bus.emit_simple(EventType.INFO, {"msg": "test1"})
        self.bus.emit_simple(EventType.WARNING, {"msg": "test2"})

        history = self.bus.get_history()
        assert len(history) >= 2

        filtered = self.bus.get_history(EventType.WARNING)
        assert len(filtered) >= 1
        assert filtered[0].data["msg"] == "test2"

    def test_clear_history(self):
        self.bus.emit_simple(EventType.INFO)
        self.bus.clear_history()
        assert len(self.bus.get_history()) == 0
