"""Load and save incidents in the existing AIRA tables.

Tables we reuse (created by the .NET migrations):
  incidents, incident_evidence, incident_hypotheses,
  incident_timeline, incident_tool_executions, knowledge_chunks
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from aira2.domain import EvidenceItem, Hypothesis, Incident, TimelineEntry
from aira2.schemas import (
    EvidenceDto,
    HypothesisDto,
    IncidentDetails,
    IncidentListItem,
    TimelineEntryDto,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        from datetime import timezone

        return value.replace(tzinfo=timezone.utc)
    return value


def list_incidents(conn) -> list[IncidentListItem]:
    rows = conn.execute(
        """
        SELECT "Id", "Reference", "Title", "Service", "Environment",
               "Severity", "Status", "CreatedAt", "UpdatedAt"
        FROM incidents
        ORDER BY "CreatedAt" DESC
        """
    ).fetchall()
    return [
        IncidentListItem(
            id=row["Id"],
            reference=row["Reference"],
            title=row["Title"],
            service=row["Service"],
            environment=row["Environment"],
            severity=row["Severity"],
            status=row["Status"],
            created_at=_as_utc(row["CreatedAt"]),
            updated_at=_as_utc(row["UpdatedAt"]),
        )
        for row in rows
    ]


def get_incident(conn, incident_id: UUID) -> Incident | None:
    row = conn.execute(
        """
        SELECT "Id", "Reference", "Title", "Description", "Service",
               "Environment", "Severity", "Status", "Risk", "CurrentPlan",
               "ResolutionSummary", "CreatedAt", "UpdatedAt"
        FROM incidents
        WHERE "Id" = %s
        """,
        (incident_id,),
    ).fetchone()
    if row is None:
        return None

    incident = Incident(
        id=row["Id"],
        reference=row["Reference"],
        title=row["Title"],
        description=row["Description"],
        service=row["Service"],
        environment=row["Environment"],
        severity=row["Severity"],
        status=row["Status"],
        risk=row["Risk"],
        current_plan=row["CurrentPlan"],
        resolution_summary=row["ResolutionSummary"],
        created_at=_as_utc(row["CreatedAt"]),
        updated_at=_as_utc(row["UpdatedAt"]),
    )
    # Loaded children are "already in the database". Only new_* lists are inserted later.
    incident.evidence = _load_evidence(conn, incident_id)
    incident.hypotheses = _load_hypotheses(conn, incident_id)
    incident.timeline = _load_timeline(conn, incident_id)
    incident.new_evidence = []
    incident.new_hypotheses = []
    incident.new_tools = []
    incident.new_timeline = []
    return incident


def _load_evidence(conn, incident_id: UUID) -> list[EvidenceItem]:
    rows = conn.execute(
        """
        SELECT "Id", "CollectedAt", "Source", "Summary", "Details"
        FROM incident_evidence
        WHERE "IncidentId" = %s
        ORDER BY "CollectedAt"
        """,
        (incident_id,),
    ).fetchall()
    return [
        EvidenceItem(
            id=row["Id"],
            collected_at=_as_utc(row["CollectedAt"]),
            source=row["Source"],
            summary=row["Summary"],
            details=row["Details"],
        )
        for row in rows
    ]


def _load_hypotheses(conn, incident_id: UUID) -> list[Hypothesis]:
    rows = conn.execute(
        """
        SELECT "Id", "CreatedAt", "Statement", "Confidence", "IsActive"
        FROM incident_hypotheses
        WHERE "IncidentId" = %s
        ORDER BY "CreatedAt"
        """,
        (incident_id,),
    ).fetchall()
    return [
        Hypothesis(
            id=row["Id"],
            created_at=_as_utc(row["CreatedAt"]),
            statement=row["Statement"],
            confidence=row["Confidence"],
            is_active=row["IsActive"],
        )
        for row in rows
    ]


def _load_timeline(conn, incident_id: UUID) -> list[TimelineEntry]:
    rows = conn.execute(
        """
        SELECT "Id", "OccurredAt", "Kind", "Message"
        FROM incident_timeline
        WHERE "IncidentId" = %s
        ORDER BY "OccurredAt"
        """,
        (incident_id,),
    ).fetchall()
    return [
        TimelineEntry(
            id=row["Id"],
            occurred_at=_as_utc(row["OccurredAt"]),
            kind=row["Kind"],
            message=row["Message"],
        )
        for row in rows
    ]


def insert_incident(conn, incident: Incident) -> None:
    conn.execute(
        """
        INSERT INTO incidents (
            "Id", "Reference", "Title", "Description", "Service", "Environment",
            "Severity", "Status", "Risk", "CurrentPlan", "ResolutionSummary",
            "CreatedAt", "UpdatedAt"
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            incident.id,
            incident.reference,
            incident.title,
            incident.description,
            incident.service,
            incident.environment,
            incident.severity,
            incident.status,
            incident.risk,
            incident.current_plan,
            incident.resolution_summary,
            incident.created_at,
            incident.updated_at,
        ),
    )
    _insert_children(conn, incident)


def save_investigation(conn, incident: Incident) -> None:
    """Update the parent row, then insert only the new child rows."""
    conn.execute(
        """
        UPDATE incidents
        SET "Status" = %s,
            "Risk" = %s,
            "CurrentPlan" = %s,
            "UpdatedAt" = %s
        WHERE "Id" = %s
        """,
        (incident.status, incident.risk, incident.current_plan, incident.updated_at, incident.id),
    )
    _insert_children(conn, incident)


def _insert_children(conn, incident: Incident) -> None:
    for item in incident.new_evidence:
        conn.execute(
            """
            INSERT INTO incident_evidence
                ("Id", "IncidentId", "CollectedAt", "Source", "Summary", "Details")
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (item.id, incident.id, item.collected_at, item.source, item.summary, item.details),
        )
    for item in incident.new_hypotheses:
        conn.execute(
            """
            INSERT INTO incident_hypotheses
                ("Id", "IncidentId", "CreatedAt", "Statement", "Confidence", "IsActive")
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (item.id, incident.id, item.created_at, item.statement, item.confidence, item.is_active),
        )
    for item in incident.new_tools:
        conn.execute(
            """
            INSERT INTO incident_tool_executions
                ("Id", "IncidentId", "ExecutedAt", "ToolName", "ServerName",
                 "Risk", "Input", "Output", "Succeeded")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                item.id,
                incident.id,
                item.executed_at,
                item.tool_name,
                item.server_name,
                item.risk,
                item.input_json,
                item.output,
                item.succeeded,
            ),
        )
    for item in incident.new_timeline:
        conn.execute(
            """
            INSERT INTO incident_timeline
                ("Id", "IncidentId", "OccurredAt", "Kind", "Message")
            VALUES (%s, %s, %s, %s, %s)
            """,
            (item.id, incident.id, item.occurred_at, item.kind, item.message),
        )


def to_details(incident: Incident) -> IncidentDetails:
    return IncidentDetails(
        id=incident.id,
        reference=incident.reference,
        title=incident.title,
        description=incident.description,
        service=incident.service,
        environment=incident.environment,
        severity=incident.severity,
        status=incident.status,
        risk=incident.risk,
        current_plan=incident.current_plan,
        resolution_summary=incident.resolution_summary,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        timeline=[
            TimelineEntryDto(
                id=e.id, occurred_at=e.occurred_at, kind=e.kind, message=e.message
            )
            for e in sorted(incident.timeline, key=lambda x: x.occurred_at)
        ],
        evidence=[
            EvidenceDto(
                id=e.id,
                collected_at=e.collected_at,
                source=e.source,
                summary=e.summary,
                details=e.details,
            )
            for e in sorted(incident.evidence, key=lambda x: x.collected_at)
        ],
        hypotheses=[
            HypothesisDto(
                id=h.id,
                created_at=h.created_at,
                statement=h.statement,
                confidence=h.confidence,
                is_active=h.is_active,
            )
            for h in sorted(incident.hypotheses, key=lambda x: x.created_at)
        ],
    )


def load_runbook_rows(conn) -> list[tuple[str, str]]:
    """Read runbook text from the C# knowledge_chunks table (Title + Content only).

    We do not reuse the nomic-embed-text vector(768) column. AIRA2 embeds
    with OpenAI (see rag.py) so the course embedding model is used.
    """
    rows = conn.execute(
        """
        SELECT "Title", "Content"
        FROM knowledge_chunks
        ORDER BY "Title"
        """
    ).fetchall()
    return [(row["Title"], row["Content"]) for row in rows]
