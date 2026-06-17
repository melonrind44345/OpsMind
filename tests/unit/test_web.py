"""Unit tests for OpsMind Web API endpoints.

Uses FastAPI TestClient with mocked OpsMindEngine to test each endpoint
in isolation without real discovery/assessment work.
"""

import json
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from opsmind import __version__
from opsmind.core.exceptions import (
    AssessmentError,
    DiscoveryError,
    OpsMindError,
    RemediationError,
    ReportGenerationError,
)
from opsmind.schemas.assessment import (
    AssessmentDimension,
    AssessmentResult,
    ComplexityAssessment,
    ComplexityLevel,
    DimensionScore,
    FeasibilityReport,
    MigrationStrategy,
    ResourceSizing,
    RiskLevel,
)
from opsmind.schemas.discovery import (
    ConfidenceLevel,
    CPUInfo,
    DataSource,
    DiscoveryMetadata,
    DiscoveryMethod,
    DiscoveryResult,
    HardwareSpec,
    MemoryInfo,
    SecurityAssessment,
    SoftwareEnvironment,
    UnifiedDiscoveryModel,
)
from opsmind.schemas.report import ReportData, ReportMetadata
from opsmind.web.app import app


@pytest.fixture
def client() -> TestClient:
    """Return a fresh TestClient for each test."""
    # Clear engine singleton between tests
    import opsmind.web.app as web_app

    web_app._engine = None
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════════
# Health & Info (existing — regression tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestHealth:
    def test_health_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "opsmind"
        assert data["version"] == __version__
        assert "uptime_seconds" in data

    def test_info_returns_platform_data(self, client: TestClient) -> None:
        response = client.get("/api/info")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "OpsMind"
        assert "python_version" in data

    def test_status_returns_operational(self, client: TestClient) -> None:
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert data["engine"] == "ready"


# ═══════════════════════════════════════════════════════════════════════════════
# Helper factories
# ═══════════════════════════════════════════════════════════════════════════════


def _make_discovery_result(hostname: str = "test-host") -> DiscoveryResult:
    """Build a minimal valid DiscoveryResult for test requests."""
    return DiscoveryResult(
        hosts={
            hostname: UnifiedDiscoveryModel(
                hardware=HardwareSpec(
                    hostname=hostname,
                    platform="linux",
                    cpu=CPUInfo(model="Intel Test", architecture="x86_64", cores=4, threads=8),
                    memory=MemoryInfo(total_gb=16.0, available_gb=8.0),
                ),
                software=SoftwareEnvironment(
                    os_name="Ubuntu",
                    os_version="22.04",
                    os_family="Debian",
                    kernel="5.15.0",
                    hostname=hostname,
                ),
                security=SecurityAssessment(firewall_active=True),
                metadata=DiscoveryMetadata(
                    method=DiscoveryMethod.MOCK,
                    source=DataSource.MOCK_DATA,
                    host=hostname,
                    confidence=ConfidenceLevel.HIGH,
                ),
            )
        },
        total_hosts=1,
        successful_hosts=1,
        failed_hosts=0,
        total_duration_ms=150.0,
    )


def _make_assessment_result(hostname: str = "test-host") -> AssessmentResult:
    """Build a minimal valid AssessmentResult for test requests."""
    return AssessmentResult(
        host=hostname,
        feasibility=FeasibilityReport(
            overall_score=72.5,
            complexity=ComplexityLevel.MODERATE,
            risk_level=RiskLevel.MEDIUM,
            dimension_scores=[
                DimensionScore(
                    dimension=AssessmentDimension.HARDWARE_COMPATIBILITY,
                    score=80.0,
                    weight=0.35,
                ),
                DimensionScore(
                    dimension=AssessmentDimension.SOFTWARE_SUPPORT,
                    score=65.0,
                    weight=0.35,
                ),
            ],
            summary="Moderate feasibility for containerization.",
            recommendations=["Update OS packages before containerizing."],
        ),
        complexity=ComplexityAssessment(
            level=ComplexityLevel.MODERATE,
            score=50.0,
            estimated_effort_days=5,
        ),
        resource_sizing=ResourceSizing(cpu_cores=2.0, memory_gb=4.0),
        migration_strategy=MigrationStrategy(
            strategy_type="rehost",
            estimated_duration_days=10,
            rollback_strategy="Revert to VM snapshot.",
        ),
        assessed_at=datetime.now(),
    )


def _make_report_data() -> ReportData:
    """Build a minimal ReportData for verifying report responses."""
    return ReportData(
        metadata=ReportMetadata(
            title="OpsMind Assessment Report",
            total_hosts=1,
            confidence="high",
        ),
        executive_summary="Test executive summary.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/discover
# ═══════════════════════════════════════════════════════════════════════════════


class TestDiscover:
    def test_discover_mock_localhost(self, client: TestClient) -> None:
        """Discover with mock method — should use real engine (no mocking needed)."""
        response = client.post(
            "/api/discover",
            json={"target": "localhost", "method": "mock"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_hosts"] >= 1
        assert data["successful_hosts"] >= 1
        assert "hosts" in data

    def test_discover_with_inventory_and_ssh(self, client: TestClient) -> None:
        response = client.post(
            "/api/discover",
            json={
                "target": "192.168.1.100",
                "method": "mock",
                "inventory": "/etc/ansible/hosts",
                "ssh_user": "admin",
                "ssh_key": "/home/admin/.ssh/id_rsa",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_hosts"] >= 1

    def test_discover_defaults_method_to_auto(self, client: TestClient) -> None:
        """When method is omitted, it should default to "auto" and succeed."""
        with patch("opsmind.web.app.OpsMindEngine.discover") as mock_discover:
            mock_discover.return_value = DiscoveryResult(hosts={}, total_hosts=0, successful_hosts=0, failed_hosts=0)
            response = client.post(
                "/api/discover",
                json={"target": "localhost"},
            )
        assert response.status_code == 200

    def test_discover_handles_engine_error(self, client: TestClient) -> None:
        with patch("opsmind.web.app.OpsMindEngine.discover", side_effect=DiscoveryError("Host unreachable")):
            response = client.post(
                "/api/discover",
                json={"target": "down-host", "method": "mock"},
            )
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "DISC_ERR"


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/assess
# ═══════════════════════════════════════════════════════════════════════════════


class TestAssess:
    def test_assess_from_discovery_result(self, client: TestClient) -> None:
        discovery = _make_discovery_result("web-server-01")
        response = client.post(
            "/api/assess",
            json={
                "discovery_result": json.loads(discovery.model_dump_json()),
                "detail_level": "detailed",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "web-server-01" in data
        host = data["web-server-01"]
        assert "feasibility" in host
        assert "complexity" in host
        assert "migration_strategy" in host

    def test_assess_default_detail_level(self, client: TestClient) -> None:
        discovery = _make_discovery_result()
        response = client.post(
            "/api/assess",
            json={"discovery_result": json.loads(discovery.model_dump_json())},
        )
        assert response.status_code == 200

    def test_assess_handles_engine_error(self, client: TestClient) -> None:
        discovery = _make_discovery_result()
        with patch("opsmind.web.app.OpsMindEngine.assess", side_effect=AssessmentError("Evaluation failed")):
            response = client.post(
                "/api/assess",
                json={"discovery_result": json.loads(discovery.model_dump_json())},
            )
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "ASMT_ERR"


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/pipeline
# ═══════════════════════════════════════════════════════════════════════════════


class TestPipeline:
    def test_pipeline_mock_localhost(self, client: TestClient) -> None:
        response = client.post(
            "/api/pipeline",
            json={"target": "localhost", "method": "mock", "report_format": "json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "discovery" in data
        assert "assessment" in data
        assert "report" in data

    def test_pipeline_with_remediation(self, client: TestClient) -> None:
        response = client.post(
            "/api/pipeline",
            json={
                "target": "localhost",
                "method": "mock",
                "report_format": "json",
                "generate_remediation": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "remediation" in data
        assert "docker" in data["remediation"]

    def test_pipeline_handles_error(self, client: TestClient) -> None:
        with patch("opsmind.web.app.OpsMindEngine.run_pipeline", side_effect=OpsMindError("Pipeline broken")):
            response = client.post(
                "/api/pipeline",
                json={"target": "localhost", "method": "mock"},
            )
        assert response.status_code == 500
        assert response.json()["error"]["message"] == "Pipeline broken"


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/report
# ═══════════════════════════════════════════════════════════════════════════════


class TestReport:
    def test_report_generation(self, client: TestClient) -> None:
        assessment = {"host-01": _make_assessment_result("host-01")}
        response = client.post(
            "/api/report",
            json={
                "assessment_results": {h: json.loads(r.model_dump_json()) for h, r in assessment.items()},
                "format": "json",
                "detail_level": "summary",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "metadata" in data
        assert "executive_summary" in data

    def test_report_handles_error(self, client: TestClient) -> None:
        assessment = {"host-01": _make_assessment_result("host-01")}
        with patch(
            "opsmind.web.app.OpsMindEngine.generate_report",
            side_effect=ReportGenerationError("Template missing"),
        ):
            response = client.post(
                "/api/report",
                json={
                    "assessment_results": {h: json.loads(r.model_dump_json()) for h, r in assessment.items()},
                },
            )
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "REP_ERR"


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/remediation
# ═══════════════════════════════════════════════════════════════════════════════


class TestRemediation:
    def test_remediation_generation(self, client: TestClient) -> None:
        assessment = {"host-01": _make_assessment_result("host-01")}
        response = client.post(
            "/api/remediation",
            json={
                "assessment_results": {h: json.loads(r.model_dump_json()) for h, r in assessment.items()},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "artifacts" in data
        assert "docker" in data["artifacts"]
        assert "migration_plan" in data["artifacts"]

    def test_remediation_handles_error(self, client: TestClient) -> None:
        assessment = {"host-01": _make_assessment_result("host-01")}
        with patch(
            "opsmind.web.app.OpsMindEngine.generate_remediation",
            side_effect=RemediationError("Docker generation failed"),
        ):
            response = client.post(
                "/api/remediation",
                json={
                    "assessment_results": {h: json.loads(r.model_dump_json()) for h, r in assessment.items()},
                },
            )
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "REMD_ERR"


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/pipeline/stream (SSE)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPipelineStream:
    def test_stream_returns_sse_content_type(self, client: TestClient) -> None:
        response = client.get("/api/pipeline/stream?target=localhost&method=mock&report_format=json")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_stream_contains_done_event(self, client: TestClient) -> None:
        response = client.get("/api/pipeline/stream?target=localhost&method=mock&report_format=json")
        content = response.text
        # Should contain SSE-formatted events
        assert "data:" in content
        # Last event should be 'done' or we should see workflow steps
        assert "done" in content or "discovery" in content


# ═══════════════════════════════════════════════════════════════════════════════
# Error response shape
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorResponseShape:
    def test_opsmind_error_response_structure(self, client: TestClient) -> None:
        with patch(
            "opsmind.web.app.OpsMindEngine.discover",
            side_effect=DiscoveryError("Boom", details={"host": "x"}, recoverable=True),
        ):
            response = client.post("/api/discover", json={"target": "x", "method": "mock"})
        err = response.json()["error"]
        assert err["code"] == "DISC_ERR"
        assert err["message"] == "Boom"
        assert err["severity"] == "error"
        assert err["details"] == {"host": "x"}
        assert err["recoverable"] is True

    def test_unexpected_exceptions_wrapped_in_domain_error(self, client: TestClient) -> None:
        """Route handlers wrap unexpected exceptions (e.g. RuntimeError) in domain errors."""
        with patch("opsmind.web.app.OpsMindEngine.discover", side_effect=RuntimeError("Something unexpected")):
            response = client.post("/api/discover", json={"target": "x", "method": "mock"})
        err = response.json()["error"]
        # RuntimeError is caught by route handler and re-raised as DiscoveryError
        assert err["code"] == "DISC_ERR"
        assert "unexpected" in err["message"].lower()
        assert err["severity"] == "error"

    def test_generic_handler_registered_for_uncaught_exceptions(self, client: TestClient) -> None:
        """The generic Exception handler is registered in the app's exception handlers."""
        from opsmind.core.exceptions import OpsMindError

        handler_registry = app.exception_handlers
        assert Exception in handler_registry, "Generic exception handler should be registered"
        assert OpsMindError in handler_registry, "OpsMindError handler should be registered"
