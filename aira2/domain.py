"""In-memory incident helpers.

C# AIRA kept these rules on the Incident class. Python keeps the same
rules here so we do not write SQL until the investigation finishes.

If the agent fails, we never call save(), so the row stays Status = New.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_reference() -> str:
    """Same style as C#: INC-yyyyMMddHHmmss-NNN"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"INC-{stamp}-{random.randint(100, 999)}"


@dataclass
class EvidenceItem:
    id: UUID
    collected_at: datetime
    source: str
    summary: str
    details: str | None


@dataclass
class Hypothesis:
    id: UUID
    created_at: datetime
    statement: str
    confidence: float
    is_active: bool = True


@dataclass
class ToolExecution:
    id: UUID
    executed_at: datetime
    tool_name: str
    server_name: str
    risk: str
    input_json: str
    output: str | None
    succeeded: bool


@dataclass
class TimelineEntry:
    id: UUID
    occurred_at: datetime
    kind: str
    message: str


@dataclass
class Incident:
    """One case the dashboard can show."""

    id: UUID
    reference: str
    title: str
    description: str
    service: str
    environment: str
    severity: str
    status: str
    risk: str
    current_plan: str | None
    resolution_summary: str | None
    created_at: datetime
    updated_at: datetime
    evidence: list[EvidenceItem] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    tool_executions: list[ToolExecution] = field(default_factory=list)
    timeline: list[TimelineEntry] = field(default_factory=list)
    # New child rows created during this request. save() inserts only these.
    new_evidence: list[EvidenceItem] = field(default_factory=list)
    new_hypotheses: list[Hypothesis] = field(default_factory=list)
    new_tools: list[ToolExecution] = field(default_factory=list)
    new_timeline: list[TimelineEntry] = field(default_factory=list)

    @staticmethod
    def create(title: str, description: str, service: str, environment: str, severity: str) -> Incident:
        incident = Incident(
            id=uuid4(),
            reference=new_reference(),
            title=title.strip(),
            description=description.strip(),
            service=service.strip(),
            environment=environment.strip(),
            severity=severity.strip(),
            status="New",
            risk="Read",
            current_plan=None,
            resolution_summary=None,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        incident._add_timeline("Created", f"Incident {incident.reference} created.")
        return incident

    def start_investigation(self, plan: str) -> None:
        """New → Investigating. Same guard as C# Incident.StartInvestigation."""
        if self.status in {"Resolved", "Escalated", "Failed"}:
            raise ValueError(f"Incident {self.reference} is already {self.status}.")
        if self.status not in {"New", "Investigating"}:
            raise ValueError(f"Cannot start investigation from status {self.status}.")
        self.current_plan = plan.strip()
        self._change_status("Investigating", "Investigation started.")

    def add_evidence(self, source: str, summary: str, details: str | None = None) -> None:
        item = EvidenceItem(
            id=uuid4(),
            collected_at=utcnow(),
            source=source,
            summary=summary,
            details=details,
        )
        self.evidence.append(item)
        self.new_evidence.append(item)
        self.updated_at = utcnow()
        self._add_timeline("EvidenceAdded", f"{source}: {summary}")

    def add_hypothesis(self, statement: str, confidence: float) -> None:
        confidence = max(0.0, min(1.0, confidence))
        item = Hypothesis(
            id=uuid4(),
            created_at=utcnow(),
            statement=statement,
            confidence=confidence,
            is_active=True,
        )
        self.hypotheses.append(item)
        self.new_hypotheses.append(item)
        self.updated_at = utcnow()
        percent = f"{confidence:.0%}"
        self._add_timeline("HypothesisUpdated", f"Hypothesis added ({percent}): {statement}")

    def record_tool(
        self,
        tool_name: str,
        server_name: str,
        input_json: str,
        output: str | None,
        succeeded: bool,
        risk: str = "Read",
    ) -> None:
        item = ToolExecution(
            id=uuid4(),
            executed_at=utcnow(),
            tool_name=tool_name,
            server_name=server_name,
            risk=risk,
            input_json=input_json,
            output=output,
            succeeded=succeeded,
        )
        self.tool_executions.append(item)
        self.new_tools.append(item)
        if risk != "Read":
            self.risk = risk
        self.updated_at = utcnow()
        verb = "succeeded" if succeeded else "failed"
        self._add_timeline("ToolExecuted", f"{server_name}/{tool_name} {verb}.")

    def _change_status(self, next_status: str, message: str) -> None:
        self.status = next_status
        self.updated_at = utcnow()
        self._add_timeline("StatusChanged", f"{message} Status is now {next_status}.")

    def _add_timeline(self, kind: str, message: str) -> None:
        entry = TimelineEntry(
            id=uuid4(),
            occurred_at=utcnow(),
            kind=kind,
            message=message,
        )
        self.timeline.append(entry)
        self.new_timeline.append(entry)
