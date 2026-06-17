"""OpsMind Web API — FastAPI application for Kubernetes deployment.

Provides health checks, API endpoints for discovery, assessment, pipeline,
reporting, and remediation — the full OpsMind modernization workflow.
"""

import asyncio
import json
import os
import sys
import threading
import time
from typing import Any, cast

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from opsmind import __version__
from opsmind.core.engine import OpsMindEngine
from opsmind.core.events import Event as BusEvent
from opsmind.core.events import EventType
from opsmind.core.exceptions import (
    AssessmentError,
    DiscoveryError,
    OpsMindError,
    RemediationError,
    ReportGenerationError,
    ValidationError,
)
from opsmind.schemas.assessment import AssessmentResult
from opsmind.schemas.discovery import DiscoveryResult

app = FastAPI(
    title="OpsMind API",
    description=(
        "Ansible-Driven Modernization Assessment Platform — discover, assess, and plan legacy system modernization"
    ),
    version=__version__,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("OPSMIND_CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup tracking ──────────────────────────────────────────────────────────
_start_time = time.time()

# ── Engine singleton ──────────────────────────────────────────────────────────
_engine: OpsMindEngine | None = None


def _get_engine() -> OpsMindEngine:
    """Get or create the OpsMind engine singleton."""
    global _engine
    if _engine is None:
        _engine = OpsMindEngine()
    return _engine


# ═══════════════════════════════════════════════════════════════════════════════
# Request Models
# ═══════════════════════════════════════════════════════════════════════════════


class DiscoverRequest(BaseModel):
    """Parameters for system discovery."""

    target: str = Field(..., description="Target hostname, IP, or inventory group (e.g., localhost, 192.168.1.100)")
    method: str = Field("auto", description="Discovery method: ansible, native, mock, auto")
    inventory: str | None = Field(None, description="Path to Ansible inventory file")
    ssh_user: str | None = Field(None, description="SSH username for remote hosts")
    ssh_key: str | None = Field(None, description="SSH private key path")


class AssessRequest(BaseModel):
    """Discovery result to assess for containerization feasibility."""

    discovery_result: DiscoveryResult = Field(..., description="Complete discovery result from /api/discover")
    detail_level: str = Field("detailed", description="Assessment detail level: executive, summary, detailed, raw")


class PipelineRequest(BaseModel):
    """Parameters for running the full discover→assess→report pipeline."""

    target: str = Field(..., description="Target hostname, IP, or group")
    method: str = Field("auto", description="Discovery method: ansible, native, mock, auto")
    report_format: str = Field("markdown", description="Report format: markdown, json, html")
    detail_level: str = Field("detailed", description="Detail level: executive, summary, detailed, raw")
    generate_remediation: bool = Field(False, description="Also generate Docker/migration-plan artifacts")
    optimize: str | None = Field(None, description="Optimization target for remediation: performance, size, cost")


class ReportRequest(BaseModel):
    """Assessment results to generate a report from."""

    assessment_results: dict[str, AssessmentResult] = Field(
        ..., description="Assessment results keyed by hostname (from /api/assess)"
    )
    format: str = Field("markdown", description="Report format: markdown, json, html")
    detail_level: str = Field("detailed", description="Report detail level")


class RemediationRequest(BaseModel):
    """Assessment results to generate remediation artifacts from."""

    assessment_results: dict[str, AssessmentResult] = Field(..., description="Assessment results keyed by hostname")
    optimize: str | None = Field(None, description="Optimization target: performance, size, cost")


# ═══════════════════════════════════════════════════════════════════════════════
# Error handling — map OpsMindError subclasses to HTTP status codes
# ═══════════════════════════════════════════════════════════════════════════════

_ERROR_STATUS: dict[type, int] = {
    DiscoveryError: 502,
    AssessmentError: 500,
    ReportGenerationError: 500,
    RemediationError: 500,
    ValidationError: 422,
}


@app.exception_handler(OpsMindError)
async def opsmind_error_handler(request: Request, exc: OpsMindError) -> JSONResponse:
    """Convert OpsMind errors to structured JSON responses."""
    return JSONResponse(
        status_code=_ERROR_STATUS.get(type(exc), 500),
        content={"error": exc.to_dict()},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
    """Catch-all handler for unexpected errors."""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc),
                "severity": "error",
                "details": {},
                "recoverable": False,
            }
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Health & Info (existing)
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/health")
async def health() -> dict[str, Any]:
    """Kubernetes liveness & readiness probe endpoint."""
    return {
        "status": "healthy",
        "service": "opsmind",
        "version": __version__,
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@app.get("/api/info")
async def info() -> dict[str, Any]:
    """Return basic platform information."""
    return {
        "name": "OpsMind",
        "description": "Ansible-Driven Modernization Assessment Platform",
        "version": __version__,
        "python_version": sys.version,
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    """Return system status with engine readiness."""
    return {
        "status": "operational",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "engine": "ready",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Core API — discover / assess / pipeline / report / remediation
# ═══════════════════════════════════════════════════════════════════════════════


@app.post("/api/discover")
async def api_discover(req: DiscoverRequest) -> dict[str, Any]:
    """Run system discovery on target host(s).

    Returns hardware specs, software inventory, and security baseline.
    """
    engine = _get_engine()
    try:
        result = engine.discover(
            target=req.target,
            method=req.method,
            inventory=req.inventory,
            ssh_user=req.ssh_user,
            ssh_key=req.ssh_key,
        )
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError(str(exc)) from exc

    return cast(dict[str, Any], json.loads(result.model_dump_json()))


@app.post("/api/assess")
async def api_assess(req: AssessRequest) -> dict[str, Any]:
    """Assess containerization feasibility from discovery results.

    Returns per-host feasibility scores, complexity ratings, risk levels,
    resource sizing recommendations, and migration strategies.
    """
    engine = _get_engine()
    try:
        results = engine.assess(req.discovery_result, detail_level=req.detail_level)
    except AssessmentError:
        raise
    except Exception as exc:
        raise AssessmentError(str(exc)) from exc

    return {host: json.loads(r.model_dump_json()) for host, r in results.items()}


@app.post("/api/pipeline")
async def api_pipeline(req: PipelineRequest) -> dict[str, Any]:
    """Run the complete discover → assess → report pipeline in one call.

    Returns all three phases' results. Optionally generates remediation artifacts.
    """
    engine = _get_engine()
    try:
        result = engine.run_pipeline(
            target=req.target,
            method=req.method,
            report_format=req.report_format,
            detail_level=req.detail_level,
            generate_remediation=req.generate_remediation,
            optimize=req.optimize,
        )
    except OpsMindError:
        raise
    except Exception as exc:
        raise OpsMindError(str(exc), code="PIPE_ERR") from exc

    response: dict[str, Any] = {
        "discovery": json.loads(result["discovery"].model_dump_json()),
        "assessment": {h: json.loads(r.model_dump_json()) for h, r in result["assessment"].items()},
        "report": json.loads(result["report"].model_dump_json()),
    }
    if "remediation" in result:
        response["remediation"] = result["remediation"]
    return response


@app.post("/api/report")
async def api_report(req: ReportRequest) -> dict[str, Any]:
    """Generate a modernization assessment report.

    Returns structured report data with executive summary, host-by-host
    assessments, and global recommendations.
    """
    engine = _get_engine()
    try:
        report_data = engine.generate_report(
            req.assessment_results,
            format=req.format,
            detail_level=req.detail_level,
        )
    except ReportGenerationError:
        raise
    except Exception as exc:
        raise ReportGenerationError(str(exc)) from exc

    return cast(dict[str, Any], json.loads(report_data.model_dump_json()))


@app.post("/api/remediation")
async def api_remediation(req: RemediationRequest) -> dict[str, Any]:
    """Generate remediation artifacts (Dockerfiles, docker-compose, migration plans).

    Returns a dict mapping artifact type to list of generated file paths.
    """
    engine = _get_engine()
    try:
        artifacts = engine.generate_remediation(
            req.assessment_results,
            optimize=req.optimize,
        )
    except RemediationError:
        raise
    except Exception as exc:
        raise RemediationError(str(exc)) from exc

    return {"artifacts": artifacts, "status": "success"}


# ═══════════════════════════════════════════════════════════════════════════════
# SSE Streaming — real-time pipeline progress via Server-Sent Events
# ═══════════════════════════════════════════════════════════════════════════════

_PIPELINE_EVENT_TYPES: tuple[EventType, ...] = (
    EventType.DISCOVERY_STARTED,
    EventType.DISCOVERY_COMPLETED,
    EventType.DISCOVERY_HOST_FAILED,
    EventType.ASSESSMENT_STARTED,
    EventType.ASSESSMENT_COMPLETED,
    EventType.REPORT_GENERATION_STARTED,
    EventType.REPORT_GENERATION_COMPLETED,
    EventType.REMEDIATION_STARTED,
    EventType.REMEDIATION_COMPLETED,
    EventType.WORKFLOW_STEP,
    EventType.ERROR,
    EventType.WARNING,
)


@app.get("/api/pipeline/stream")
async def api_pipeline_stream(
    target: str = Query(..., description="Target hostname, IP, or group"),
    method: str = Query("auto", description="Discovery method"),
    report_format: str = Query("markdown", description="Report format"),
    detail_level: str = Query("detailed", description="Detail level"),
    generate_remediation: bool = Query(False, description="Also generate remediation artifacts"),
) -> StreamingResponse:
    """Run the pipeline with real-time event streaming via Server-Sent Events.

    Streams progress events (discovery started/completed, assessment phases,
    etc.) as they occur. The final event is 'done' or 'error'.
    """
    engine = _get_engine()
    event_bus = engine.event_bus
    collected: list[dict[str, Any]] = []
    done = threading.Event()
    pipeline_error: str | None = None

    def collect(event: BusEvent) -> None:
        collected.append(
            {
                "type": event.type.value,
                "timestamp": event.timestamp.isoformat(),
                "data": event.data,
            }
        )

    def run_pipeline() -> None:
        nonlocal pipeline_error
        try:
            engine.run_pipeline(
                target=target,
                method=method,
                report_format=report_format,
                detail_level=detail_level,
                generate_remediation=generate_remediation,
            )
        except Exception as exc:
            pipeline_error = str(exc)
        finally:
            done.set()

    for et in _PIPELINE_EVENT_TYPES:
        event_bus.subscribe(et, collect)

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()

    async def event_stream() -> Any:
        last_idx = 0
        while not done.is_set() or last_idx < len(collected):
            while last_idx < len(collected):
                yield f"data: {json.dumps(collected[last_idx])}\n\n"
                last_idx += 1
            if done.is_set():
                break
            await asyncio.sleep(0.1)

        if pipeline_error:
            yield f"data: {json.dumps({'type': 'error', 'message': pipeline_error})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'done', 'message': 'pipeline complete'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
