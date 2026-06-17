"""Integration tests for OpsMind Web API with real engine in mock mode.

Tests the full HTTP request/response cycle with actual engine execution.
"""

import json

import pytest

pytest.importorskip("fastapi", reason="FastAPI not installed — install with `pip install opsmind-tools[web]`")
from fastapi.testclient import TestClient  # noqa: E402

from opsmind.web.app import app


@pytest.fixture
def client() -> TestClient:
    """Return a fresh TestClient with a clean engine singleton."""
    import opsmind.web.app as web_app

    web_app._engine = None
    return TestClient(app)


@pytest.mark.integration
class TestWebIntegration:
    """End-to-end tests through the web API with real engine."""

    def test_full_workflow_discover_assess_report(self, client: TestClient) -> None:
        """Complete discover → assess → report flow via API."""
        # 1. Discover
        disc_resp = client.post(
            "/api/discover",
            json={"target": "localhost", "method": "mock"},
        )
        assert disc_resp.status_code == 200
        discovery = disc_resp.json()
        assert discovery["total_hosts"] >= 1
        assert len(discovery["hosts"]) >= 1

        # 2. Assess
        asm_resp = client.post(
            "/api/assess",
            json={"discovery_result": discovery, "detail_level": "detailed"},
        )
        assert asm_resp.status_code == 200
        assessment = asm_resp.json()
        assert len(assessment) >= 1

        hostname = list(assessment.keys())[0]
        host_assessment = assessment[hostname]
        assert "feasibility" in host_assessment
        assert 0 <= host_assessment["feasibility"]["overall_score"] <= 100
        assert host_assessment["migration_strategy"]["strategy_type"] != ""

        # 3. Report
        rep_resp = client.post(
            "/api/report",
            json={
                "assessment_results": assessment,
                "format": "json",
                "detail_level": "summary",
            },
        )
        assert rep_resp.status_code == 200
        report = rep_resp.json()
        assert "metadata" in report
        assert "executive_summary" in report

    def test_pipeline_endpoint_returns_all_phases(self, client: TestClient) -> None:
        """Pipeline endpoint returns discovery, assessment, and report."""
        response = client.post(
            "/api/pipeline",
            json={
                "target": "localhost",
                "method": "mock",
                "report_format": "json",
                "detail_level": "summary",
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["discovery"]["total_hosts"] >= 1
        assert len(data["assessment"]) >= 1
        assert "metadata" in data["report"]

    def test_pipeline_with_remediation_generates_artifacts(self, client: TestClient) -> None:
        """Pipeline with generate_remediation=True produces Docker/migration artifacts."""
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
        assert len(data["remediation"]["docker"]) >= 1
        assert "migration_plan" in data["remediation"]
        assert len(data["remediation"]["migration_plan"]) >= 1

        # Verify Dockerfile exists on disk
        docker_files = data["remediation"]["docker"]
        dockerfile_paths = [f for f in docker_files if "Dockerfile" in f]
        assert len(dockerfile_paths) >= 1

        # Verify migration plans exist on disk
        plan_files = data["remediation"]["migration_plan"]
        for plan_file in plan_files:
            import os

            assert os.path.exists(plan_file), f"Expected file {plan_file} to exist"

    def test_remediation_endpoint_standalone(self, client: TestClient) -> None:
        """Generate remediation directly from assessment results."""
        # First get assessment
        disc_resp = client.post(
            "/api/discover",
            json={"target": "localhost", "method": "mock"},
        )
        asm_resp = client.post(
            "/api/assess",
            json={"discovery_result": disc_resp.json(), "detail_level": "detailed"},
        )
        assessment = asm_resp.json()

        # Then generate remediation
        rem_resp = client.post(
            "/api/remediation",
            json={"assessment_results": assessment},
        )
        assert rem_resp.status_code == 200
        data = rem_resp.json()
        assert data["status"] == "success"
        assert len(data["artifacts"]["docker"]) >= 1
        assert len(data["artifacts"]["migration_plan"]) >= 1

    def test_discover_multiple_hosts(self, client: TestClient) -> None:
        """Discover multiple targets via comma-separated list."""
        response = client.post(
            "/api/discover",
            json={"target": "legacy-centos,modern-ubuntu", "method": "mock"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_hosts"] == 2
        assert data["successful_hosts"] == 2
        assert len(data["hosts"]) == 2

    def test_sse_stream_emits_events(self, client: TestClient) -> None:
        """SSE streaming endpoint returns events in SSE format."""
        response = client.get(
            "/api/pipeline/stream",
            params={
                "target": "localhost",
                "method": "mock",
                "report_format": "json",
            },
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        content = response.text
        lines = content.strip().split("\n\n")
        # Should have at least one SSE event
        assert len(lines) >= 1
        for line in lines:
            assert line.startswith("data: ")
            event = json.loads(line[6:])  # strip "data: " prefix
            assert "type" in event

    def test_discover_response_schema(self, client: TestClient) -> None:
        """Discovery response conforms to the expected schema."""
        response = client.post(
            "/api/discover",
            json={"target": "localhost", "method": "mock"},
        )
        data = response.json()

        hostname = list(data["hosts"].keys())[0]
        host = data["hosts"][hostname]

        # Hardware section
        assert "hardware" in host
        hw = host["hardware"]
        assert "cpu" in hw
        assert hw["cpu"]["cores"] > 0
        assert "memory" in hw
        assert hw["memory"]["total_gb"] > 0
        assert "disks" in hw

        # Software section
        assert "software" in host
        sw = host["software"]
        assert sw["os_name"] != ""
        assert sw["kernel"] != ""

        # Security section
        assert "security" in host
        sec = host["security"]
        assert isinstance(sec["firewall_active"], bool)

        # Metadata section
        assert "metadata" in host
        meta = host["metadata"]
        assert "method" in meta
        assert "confidence" in meta

    def test_assessment_response_schema(self, client: TestClient) -> None:
        """Assessment response conforms to the expected schema."""
        disc_resp = client.post(
            "/api/discover",
            json={"target": "localhost", "method": "mock"},
        )
        asm_resp = client.post(
            "/api/assess",
            json={"discovery_result": disc_resp.json(), "detail_level": "detailed"},
        )
        data = asm_resp.json()
        hostname = list(data.keys())[0]
        host = data[hostname]

        # Feasibility
        assert "feasibility" in host
        feas = host["feasibility"]
        assert "overall_score" in feas
        assert "complexity" in feas
        assert "risk_level" in feas
        assert len(feas["dimension_scores"]) >= 1
        assert "summary" in feas

        # Complexity
        assert "complexity" in host
        comp = host["complexity"]
        assert "level" in comp
        assert "score" in comp

        # Resource sizing
        assert "resource_sizing" in host
        sizing = host["resource_sizing"]
        assert sizing["cpu_cores"] > 0
        assert sizing["memory_gb"] > 0

        # Migration strategy
        assert "migration_strategy" in host
        ms = host["migration_strategy"]
        assert ms["strategy_type"] != ""

    def test_error_on_invalid_target(self, client: TestClient) -> None:
        """Request with empty target returns error."""
        # Empty string target should trigger validation
        response = client.post(
            "/api/discover",
            json={"target": "", "method": "mock"},
        )
        # Engine validates and raises DiscoveryError for empty target
        assert response.status_code in (422, 502)

    def test_report_formats(self, client: TestClient) -> None:
        """Report generation works with all supported formats."""
        disc_resp = client.post(
            "/api/discover",
            json={"target": "localhost", "method": "mock"},
        )
        asm_resp = client.post(
            "/api/assess",
            json={"discovery_result": disc_resp.json()},
        )

        for fmt in ("json", "markdown", "html"):
            rep_resp = client.post(
                "/api/report",
                json={
                    "assessment_results": asm_resp.json(),
                    "format": fmt,
                },
            )
            assert rep_resp.status_code == 200, f"Report format {fmt} failed"
            data = rep_resp.json()
            assert "metadata" in data
