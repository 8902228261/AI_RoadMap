"""FastAPI entry point.

Request flow (same as C# Program.cs + IncidentEndpoints):

  browser  →  /api/incidents/...  →  repository + domain
  browser  →  POST .../investigate →  domain.start_investigation
                                   →  LangGraph (retrieve/plan/act/conclude)
                                   →  save to the same Postgres tables
  browser  →  /mcp/...            →  same simulated payloads as C# AIRA
  browser  →  /                   →  the original AIRA dashboard HTML/JS
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from aira2.agent_graph import investigate
from aira2.config import settings
from aira2.database import get_connection
from aira2.domain import Incident
from aira2 import mcp_payloads
from aira2.rag import build_vector_store
from aira2.repository import (
    get_incident,
    insert_incident,
    list_incidents,
    save_investigation,
    to_details,
)
from aira2.schemas import CreateIncidentRequest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("aira2")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown for the API process.

    Code before `yield` runs once when uvicorn starts (embed runbooks).
    Code after `yield` would run on shutdown; we have nothing to close yet.
    """
    logger.info("AIRA2 starting. UI=%s DB=%s", settings.ui_path, settings.database_url)
    build_vector_store()
    logger.info("Runbook vector store is ready.")
    yield


app = FastAPI(title="AIRA2", version="0.1.0", lifespan=lifespan)


def json_model(model) -> JSONResponse:
    """Dump Pydantic models with camelCase keys so app.js can read them."""
    return JSONResponse(content=model.model_dump(by_alias=True, mode="json"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/info")
def api_info() -> dict:
    """Dashboard pings this to show 'api online'."""
    return {
        "name": "AIRA2",
        "description": "AI-Native Incident Resolution Agent (LangChain / Python)",
        "version": "0.1.0",
        "llm": settings.chat_model,
        "embeddings": settings.embedding_model,
        "provider": "openai-langchain",
        "sameDatabaseAs": "AIRA .NET",
    }


@app.get("/api/incidents")
def api_list_incidents():
    with get_connection() as conn:
        items = list_incidents(conn)
    return JSONResponse(content=[item.model_dump(by_alias=True, mode="json") for item in items])


@app.get("/api/incidents/{incident_id}")
def api_get_incident(incident_id: UUID):
    with get_connection() as conn:
        incident = get_incident(conn, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail={"error": f"Incident {incident_id} was not found."})
    return json_model(to_details(incident))


@app.post("/api/incidents", status_code=201)
def api_create_incident(request: CreateIncidentRequest):
    incident = Incident.create(
        request.title, request.description, request.service, request.environment, request.severity
    )
    with get_connection() as conn:
        insert_incident(conn, incident)
    return json_model(to_details(incident))


@app.post("/api/incidents/demo/payment-gateway-failure", status_code=201)
def api_seed_demo():
    """Same INC-001 seed as C# AIRA. Status stays New until Investigate is clicked."""
    incident = Incident.create(
        "Payment gateway credential failure",
        "Checkout is failing with 401/403 responses from the payment gateway. This is the first vertical slice: INC-001.",
        "payments-api",
        "sim",
        "high",
    )
    with get_connection() as conn:
        insert_incident(conn, incident)
    return json_model(to_details(incident))


@app.post("/api/incidents/{incident_id}/investigate")
def api_investigate(incident_id: UUID):
    """The dashboard 'Start investigation' button.

    1. Load the case.
    2. Flip status to Investigating in memory.
    3. Run LangGraph (this talks to OpenAI).
    4. Save evidence / hypothesis / timeline in one transaction.
    If step 3 throws, we never reach step 4, so Postgres still says New.
    """
    with get_connection() as conn:
        incident = get_incident(conn, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail={"error": f"Incident {incident_id} was not found."})

    incident.start_investigation("Observe → Retrieve → Plan → Act → Verify")
    try:
        investigate(incident)
    except Exception as exc:
        logger.exception("Investigation failed")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "hint": "Check OPENAI_API_KEY, CHAT_MODEL, and that Postgres is running.",
            },
        ) from exc

    with get_connection() as conn:
        save_investigation(conn, incident)
        saved = get_incident(conn, incident.id)
    return json_model(to_details(saved or incident))


# ---------- MCP HTTP surface (same paths as C# McpEndpoints) ----------


@app.get("/mcp/connect")
def mcp_connect() -> dict:
    return {
        "protocol": "aira-mcp-http",
        "chargeable": False,
        "servers": [
            {"name": "application", "tools": mcp_payloads.list_application_tools()},
            {"name": "infrastructure", "tools": [{"name": "get_container_status", "risk": "read"}]},
        ],
    }


@app.get("/mcp/application/tools")
def mcp_application_tools():
    return mcp_payloads.list_application_tools()


@app.get("/mcp/application/get_service_health")
def mcp_health(service: str = "payments-api"):
    return mcp_payloads.get_service_health(service)


@app.get("/mcp/application/get_recent_errors")
def mcp_errors(service: str = "payments-api"):
    return mcp_payloads.get_recent_errors(service)


@app.get("/mcp/application/get_recent_deployments")
def mcp_deployments(service: str = "payments-api"):
    return mcp_payloads.get_recent_deployments(service)


@app.get("/mcp/infrastructure/get_container_status")
def mcp_container(service: str = "payments-api"):
    return mcp_payloads.get_container_status(service)


# ---------- Same UI folder as C# AIRA ----------
# Mounted last so /api and /mcp keep winning. html=True serves index.html at /.

if settings.ui_path.is_dir():
    app.mount("/", StaticFiles(directory=settings.ui_path, html=True), name="ui")
else:
    logger.warning("Dashboard folder not found: %s", settings.ui_path)
