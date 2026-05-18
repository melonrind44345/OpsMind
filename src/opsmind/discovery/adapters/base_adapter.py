"""Base adapter for converting raw discovery data to unified models."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from opsmind.schemas.discovery import UnifiedDiscoveryModel


class BaseAdapter(ABC):
    """Abstract base for data adapters."""

    @abstractmethod
    def to_unified_model(self, raw_data: Dict[str, Any]) -> UnifiedDiscoveryModel:
        """Convert raw discovery data to unified model."""
        ...
