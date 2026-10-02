"""Investigation workflow as a LangGraph.

C# AIRA: LocalAgentOrchestrator did Retrieve → Plan → Act → Conclude.
AIRA2 keeps that same order as four graph nodes so you can see each step
in LangSmith (course Module 3 tracing idea).

What each node uses from the academy:
  retrieve  — bonus_rag.ipynb (embeddings + vector store)
  plan      — 1.1_foundational_models.ipynb (init_chat_model)
  act       — create_agent + @tool + middleware (modules 1–3)
  conclude  — structured JSON, same contract as C# AIRA
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRequest,
    ModelResponse,
    dynamic_prompt,
    wrap_model_call,
)
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from aira2.config import settings
from aira2.domain import Incident
from aira2.rag import search_runbooks
from aira2.tools import mcp_tools

logger = logging.getLogger("aira2.agent")


class InvestigationState(TypedDict, total=False):
    """Data that travels from node to node. LangGraph passes this dict around."""

    title: str
    description: str
    service: str
    environment: str
    reference: str
    runbooks: list[dict]
    plan: str
    tool_messages: list[dict]
    hypothesis: str
    confidence: float
    next_action: str


class Conclusion(BaseModel):
    """The JSON the last LLM call must produce. Same fields as C# AIRA."""

    hypothesis: str = Field(description="What is most likely wrong.")
    confidence: float = Field(description="Number between 0 and 1.")
    next_action: str = Field(description="Safe next step. Do not rotate secrets.")


@wrap_model_call
def log_model_calls(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    """Middleware from Module 3: runs around every model call.

    Here we only log. In the email-agent homework this same hook swapped tools.
    """
    logger.info("LangChain model call. messages=%s", len(request.messages))
    return handler(request)


@dynamic_prompt
def act_system_prompt(request: ModelRequest) -> str:
    """Middleware from Module 3: builds the system prompt for the Act agent."""
    return (
        "You are AIRA, an incident investigator.\n"
        "Call get_service_health and get_recent_errors for the given service.\n"
        "You may also call get_recent_deployments or get_container_status if useful.\n"
        "Do not rotate credentials. Do not restart production.\n"
        "After the tools return, write a short summary of what you observed."
    )


def retrieve_node(state: InvestigationState) -> dict:
    """Step 1 — RAG. Same job as IKnowledgeRetriever in C#."""
    query = f"{state['title']}. {state['description']}. service={state['service']}"
    logger.info("RAG query: %s", query)
    runbooks = search_runbooks(query, limit=3)
    return {"runbooks": runbooks}


def plan_node(state: InvestigationState) -> dict:
    """Step 2 — LLM plan. Same job as the first Ollama chat in C#."""
    runbook_text = "No runbooks retrieved."
    if state.get("runbooks"):
        runbook_text = "\n\n".join(
            f"{item['title']}: {item['content']}" for item in state["runbooks"]
        )

    model = init_chat_model(model=settings.chat_model)
    response = model.invoke(
        [
            (
                "system",
                "You are AIRA, an incident investigator. Use only the supplied "
                "runbook and incident. Do not invent production actions. "
                "Reply in 3 short sentences.",
            ),
            (
                "human",
                f"""Incident: {state['title']}
Details: {state['description']}
Service: {state['service']}
Environment: {state['environment']}

Runbooks:
{runbook_text}

What should we inspect first?""",
            ),
        ]
    )
    plan = _message_text(response)
    logger.info("Plan: %s", plan[:200])
    return {"plan": plan}


def act_node(state: InvestigationState) -> dict:
    """Step 3 — tool-calling agent (create_agent).

    C# called MCP over HTTP. AIRA2 uses the same payloads as LangChain tools
    so the course create_agent loop is visible. FastAPI still exposes /mcp
    so you can also open those URLs in a browser.
    """
    agent = create_agent(
        model=settings.chat_model,
        tools=mcp_tools(),
        middleware=[log_model_calls, act_system_prompt],
    )
    result = agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        f"Incident {state['reference']}: {state['title']}. "
                        f"Service={state['service']}. Environment={state['environment']}.\n"
                        f"Plan we already wrote: {state.get('plan', '')}\n"
                        "Call get_service_health and get_recent_errors now."
                    )
                )
            ]
        }
    )
    tool_messages = _extract_tool_results(result.get("messages", []))
    logger.info("Act collected %s tool result(s).", len(tool_messages))
    return {"tool_messages": tool_messages}


def conclude_node(state: InvestigationState) -> dict:
    """Step 4 — JSON conclusion. Same contract as C# TryParseConclusion."""
    evidence_lines = []
    for book in state.get("runbooks", []):
        evidence_lines.append(f"- rag: {book['title']}. {book['content']}")
    if state.get("plan"):
        evidence_lines.append(f"- llm plan: {state['plan']}")
    for tool in state.get("tool_messages", []):
        evidence_lines.append(f"- mcp:{tool['name']}: {tool['content']}")

    model = init_chat_model(model=settings.chat_model)
    # with_structured_output asks the model for our Pydantic shape.
    structured = model.with_structured_output(Conclusion)
    try:
        parsed = structured.invoke(
            [
                (
                    "system",
                    "You are AIRA. Conclude from evidence only. "
                    "Do not rotate credentials or restart production.",
                ),
                (
                    "human",
                    f"Incident {state['reference']}\n" + "\n".join(evidence_lines),
                ),
            ]
        )
        return {
            "hypothesis": parsed.hypothesis,
            "confidence": float(parsed.confidence),
            "next_action": parsed.next_action,
        }
    except Exception as exc:
        logger.warning("Structured conclude failed (%s). Falling back to free text.", exc)
        raw = model.invoke(
            [
                (
                    "system",
                    'Reply with JSON only: {"hypothesis":"...","confidence":0.0,"nextAction":"..."}',
                ),
                ("human", "\n".join(evidence_lines)),
            ]
        )
        return _parse_conclusion(_message_text(raw))


def _message_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
        return "\n".join(parts).strip()
    return str(content).strip()


def _extract_tool_results(messages: list) -> list[dict]:
    """Walk the create_agent transcript and keep ToolMessage payloads."""
    results: list[dict] = []
    for message in messages:
        # LangChain ToolMessage has .type == "tool" and .name
        name = getattr(message, "name", None)
        msg_type = getattr(message, "type", "")
        if msg_type == "tool" and name:
            results.append({"name": name, "content": _message_text(message)})
    return results


def _parse_conclusion(text: str) -> dict:
    match = re.search(r"\{.*\}", text, flags=re.S)
    blob = match.group(0) if match else text
    try:
        data = json.loads(blob)
        return {
            "hypothesis": data.get("hypothesis", text[:400]),
            "confidence": float(data.get("confidence", 0.6)),
            "next_action": data.get("nextAction") or data.get("next_action") or "Escalate for human review.",
        }
    except json.JSONDecodeError:
        return {
            "hypothesis": text[:400],
            "confidence": 0.5,
            "next_action": "Review evidence with a human.",
        }


def build_graph():
    """Compile the four-step graph. Call once at startup."""
    graph = StateGraph(InvestigationState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("plan", plan_node)
    graph.add_node("act", act_node)
    graph.add_node("conclude", conclude_node)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "plan")
    graph.add_edge("plan", "act")
    graph.add_edge("act", "conclude")
    graph.add_edge("conclude", END)
    return graph.compile()


investigation_graph = None


def get_graph():
    global investigation_graph
    if investigation_graph is None:
        investigation_graph = build_graph()
    return investigation_graph


def apply_result_to_incident(incident: Incident, result: InvestigationState) -> None:
    """Copy graph output onto the incident so the repository can save it.

    This is the Python version of C# AddEvidence / RecordToolExecution / AddHypothesis.
    """
    for book in result.get("runbooks", []):
        incident.add_evidence(
            "rag",
            f"Retrieved {book['title']} (score {book.get('score', 0):.2f})",
            book["content"],
        )

    if result.get("plan"):
        incident.add_evidence(
            "llm",
            f"Investigation plan from {settings.chat_model}",
            result["plan"],
        )

    server_for = {
        "get_service_health": "application",
        "get_recent_errors": "application",
        "get_recent_deployments": "application",
        "get_container_status": "infrastructure",
        "search_web": "web",
    }
    for tool in result.get("tool_messages", []):
        name = tool["name"]
        server = server_for.get(name, "application")
        incident.record_tool(
            tool_name=name,
            server_name=server,
            input_json=json.dumps({"service": incident.service}),
            output=tool["content"],
            succeeded=True,
        )
        incident.add_evidence(
            f"mcp:{server}/{name}",
            f"{name} returned evidence",
            tool["content"],
        )

    incident.add_hypothesis(result.get("hypothesis") or "No hypothesis", float(result.get("confidence") or 0.5))
    incident.add_evidence("llm", "Recommended next action", result.get("next_action") or "Escalate.")


def investigate(incident: Incident) -> None:
    """Run the graph and write evidence onto the incident (still in memory)."""
    settings.require_openai()
    graph = get_graph()
    result = graph.invoke(
        {
            "title": incident.title,
            "description": incident.description,
            "service": incident.service,
            "environment": incident.environment,
            "reference": incident.reference,
        }
    )
    apply_result_to_incident(incident, result)
    logger.info("AIRA2 finished %s.", incident.reference)
