"""Custom exceptions for OpsMind with error codes and severity levels."""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorSeverity(Enum):
    """Severity levels for errors."""

    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class OpsMindError(Exception):
    """Base exception for all OpsMind errors."""

    def __init__(
        self,
        message: str,
        code: str = "OPSMIND_ERR",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = False,
    ) -> None:
        self.message = message
        self.code = code
        self.severity = severity
        self.details = details or {}
        self.recoverable = recoverable
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "details": self.details,
            "recoverable": self.recoverable,
        }


class DiscoveryError(OpsMindError):
    """Errors during discovery phase."""

    def __init__(
        self,
        message: str,
        code: str = "DISC_ERR",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
    ) -> None:
        super().__init__(message, code, severity, details, recoverable)


class AnsibleError(DiscoveryError):
    """Ansible-specific errors."""

    def __init__(
        self,
        message: str,
        code: str = "ANS_ERR",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
    ) -> None:
        super().__init__(message, code, severity, details, recoverable)


class AnsibleNotAvailableError(AnsibleError):
    """Ansible is not installed or not available."""

    def __init__(
        self,
        message: str = "Ansible is not available on this system",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ANS_NOT_FOUND",
            severity=ErrorSeverity.WARNING,
            details=details,
            recoverable=True,
        )


class SSHConnectionError(AnsibleError):
    """SSH connection failure."""

    def __init__(
        self,
        host: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message or f"SSH connection failed to {host}",
            code="ANS_SSH_FAIL",
            severity=ErrorSeverity.ERROR,
            details={"host": host, **(details or {})},
            recoverable=True,
        )


class NativeDiscoveryError(DiscoveryError):
    """Native discovery failures."""

    def __init__(
        self,
        message: str,
        code: str = "NAT_ERR",
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
    ) -> None:
        super().__init__(message, code, severity, details, recoverable)


class AssessmentError(OpsMindError):
    """Errors during assessment phase."""

    def __init__(
        self,
        message: str,
        code: str = "ASMT_ERR",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message, code, severity, details, recoverable)


class ReportGenerationError(OpsMindError):
    """Errors during report generation."""

    def __init__(
        self,
        message: str,
        code: str = "REP_ERR",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
    ) -> None:
        super().__init__(message, code, severity, details, recoverable)


class RemediationError(OpsMindError):
    """Errors during remediation generation."""

    def __init__(
        self,
        message: str,
        code: str = "REMD_ERR",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
    ) -> None:
        super().__init__(message, code, severity, details, recoverable)


class ValidationError(OpsMindError):
    """Data validation errors."""

    def __init__(
        self,
        message: str,
        code: str = "VAL_ERR",
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
    ) -> None:
        super().__init__(message, code, severity, details, recoverable)
