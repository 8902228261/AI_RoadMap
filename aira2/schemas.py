"""API shapes that match the C# AIRA dashboard.

The browser (ui/aira-dashboard/app.js) expects camelCase JSON and
string enums such as status: "New". If a field name changes, the UI breaks.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _camel(name: str) -> str:
    """created_at → createdAt. Pydantic uses this for JSON keys."""
    parts = name.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=_camel,
        ser_json_timedelta="iso8601",
    )


class CreateIncidentRequest(CamelModel):
    title: str
    description: str
    service: str
    environment: str
    severity: str


class IncidentListItem(CamelModel):
    id: UUID
    reference: str
    title: str
    service: str
    environment: str
    severity: str
    status: str
    created_at: datetime
    updated_at: datetime


class TimelineEntryDto(CamelModel):
    id: UUID
    occurred_at: datetime
    kind: str
    message: str


class EvidenceDto(CamelModel):
    id: UUID
    collected_at: datetime
    source: str
    summary: str
    details: str | None = None


class HypothesisDto(CamelModel):
    id: UUID
    created_at: datetime
    statement: str
    confidence: float
    is_active: bool


class IncidentDetails(CamelModel):
    id: UUID
    reference: str
    title: str
    description: str
    service: str
    environment: str
    severity: str
    status: str
    risk: str
    current_plan: str | None = Field(default=None)
    resolution_summary: str | None = Field(default=None)
    created_at: datetime
    updated_at: datetime
    timeline: list[TimelineEntryDto]
    evidence: list[EvidenceDto]
    hypotheses: list[HypothesisDto]
