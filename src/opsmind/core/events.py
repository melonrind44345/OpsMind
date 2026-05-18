"""Event system for OpsMind workflow tracking."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class EventType(Enum):
    """Types of events in the OpsMind workflow."""

    # Discovery events
    DISCOVERY_STARTED = "discovery.started"
    DISCOVERY_HOST_STARTED = "discovery.host.started"
    DISCOVERY_HOST_COMPLETED = "discovery.host.completed"
    DISCOVERY_HOST_FAILED = "discovery.host.failed"
    DISCOVERY_COMPLETED = "discovery.completed"

    # Engine events
    ENGINE_FALLBACK = "engine.fallback"
    ENGINE_RETRY = "engine.retry"
    ENGINE_DEGRADED = "engine.degraded"

    # Assessment events
    ASSESSMENT_STARTED = "assessment.started"
    ASSESSMENT_DIMENSION_EVALUATED = "assessment.dimension.evaluated"
    ASSESSMENT_COMPLETED = "assessment.completed"

    # Report events
    REPORT_GENERATION_STARTED = "report.generation.started"
    REPORT_SECTION_GENERATED = "report.section.generated"
    REPORT_GENERATION_COMPLETED = "report.generation.completed"

    # Remediation events
    REMEDIATION_STARTED = "remediation.started"
    REMEDIATION_COMPLETED = "remediation.completed"

    # General events
    WORKFLOW_STEP = "workflow.step"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Event:
    """A workflow event."""

    type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None


EventHandler = Callable[[Event], None]


class EventBus:
    """Simple event bus for inter-component communication."""

    _instance: Optional["EventBus"] = None

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers = {}
            cls._instance._history = []
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_handlers"):
            self._handlers: Dict[EventType, List[EventHandler]] = {}
            self._history: List[Event] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from a specific event type."""
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]

    def emit(self, event: Event) -> None:
        """Emit an event to all subscribers."""
        self._history.append(event)
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                pass  # Prevent handler errors from breaking the chain

    def emit_simple(self, event_type: EventType, data: Optional[Dict[str, Any]] = None) -> None:
        """Emit a simple event with just type and optional data."""
        self.emit(Event(type=event_type, data=data or {}))

    def get_history(self, event_type: Optional[EventType] = None) -> List[Event]:
        """Get event history, optionally filtered by type."""
        if event_type:
            return [e for e in self._history if e.type == event_type]
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear all event history."""
        self._history.clear()

    def reset(self) -> None:
        """Reset the event bus (clear handlers and history)."""
        self._handlers.clear()
        self._history.clear()
