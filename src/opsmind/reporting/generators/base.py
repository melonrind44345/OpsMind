"""Base report generator interface."""

from abc import ABC, abstractmethod

from opsmind.schemas.assessment import AssessmentResult
from opsmind.schemas.report import DetailLevel, ReportData


class BaseReportGenerator(ABC):
    """Abstract base for report generators."""

    def __init__(self, output_dir: str | None = None) -> None:
        self.output_dir = output_dir

    @abstractmethod
    def generate(self, assessment_results: dict[str, AssessmentResult], detail_level: DetailLevel) -> ReportData:
        """Generate report data from assessment results."""
        ...

    @abstractmethod
    def export(self, report_data: ReportData, output_path: str) -> str:
        """Export report to a file."""
        ...
