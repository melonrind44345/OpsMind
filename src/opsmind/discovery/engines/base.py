"""Base discovery engine interface."""

from abc import ABC, abstractmethod

from opsmind.schemas.discovery import DiscoveryMetadata, DiscoveryMethod, DiscoveryResult


class BaseDiscoveryEngine(ABC):
    """Abstract base for all discovery engines."""

    @property
    @abstractmethod
    def method(self) -> DiscoveryMethod:
        """Return the discovery method this engine implements."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this engine is available on the current system."""
        ...

    @abstractmethod
    def discover_host(self, host: str) -> DiscoveryResult:
        """Discover a single host and return structured result."""
        ...

    @abstractmethod
    def discover_group(self, hosts: list[str], parallel: bool = True) -> DiscoveryResult:
        """Discover multiple hosts, optionally in parallel."""
        ...

    def _create_metadata(self, host: str, source: str, duration_ms: float = 0.0) -> DiscoveryMetadata:
        """Create base discovery metadata."""
        from datetime import datetime

        from opsmind.schemas.discovery import DataSource

        try:
            source_enum = DataSource(source)
        except ValueError:
            source_enum = DataSource.HEURISTIC_INFERENCE

        return DiscoveryMetadata(
            method=self.method,
            source=source_enum,
            collected_at=datetime.now(),
            collection_duration_ms=duration_ms,
            host=host,
        )
