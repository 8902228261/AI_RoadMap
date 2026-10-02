"""Simulated MCP tool payloads — same JSON as C# ApplicationMcpTools.

The HTTP call is real (this FastAPI process). The payments-api data is fake
so INC-001 can run without a real payment stack.
"""

from __future__ import annotations


def list_application_tools() -> list[dict]:
    return [
        {"name": "get_service_health", "risk": "read", "description": "Return simulated service health."},
        {"name": "get_recent_errors", "risk": "read", "description": "Return simulated recent errors."},
        {
            "name": "get_recent_deployments",
            "risk": "read",
            "description": "Return simulated recent deployments.",
        },
    ]


def get_service_health(service: str) -> dict:
    if service == "payments-api":
        return {
            "service": service,
            "status": "degraded",
            "checks": ["auth-gateway"],
            "detail": "Payment gateway authentication is failing.",
        }
    return {
        "service": service,
        "status": "healthy",
        "checks": [],
        "detail": "No simulated fault.",
    }


def get_recent_errors(service: str) -> dict:
    if service == "payments-api":
        return {
            "service": service,
            "errors": [
                {
                    "timestamp": "2026-08-22T12:00:00Z",
                    "status": 401,
                    "message": "gateway credentials rejected",
                }
            ],
        }
    return {"service": service, "errors": []}


def get_recent_deployments(service: str) -> dict:
    return {
        "service": service,
        "deployments": [
            {"version": "2026.8.22.1", "at": "2026-08-21T18:00:00Z", "result": "success"}
        ],
    }


def get_container_status(service: str) -> dict:
    return {"service": service, "state": "running", "restarts": 0}
