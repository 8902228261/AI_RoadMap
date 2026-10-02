"""LangChain tools the investigation agent can call.

Course mapping:
  Module 1 lesson 1.2  → @tool
  Module 2 bonus_rag   → a retrieve tool over a vector store
  Module 1 lesson 1.2  → optional Tavily web search
  Module 2 lesson 2.1  → MCP-style tools (here they are Python functions;
                         FastAPI also exposes the same payloads at /mcp/...)
"""

from __future__ import annotations

import json
import logging

from langchain.tools import tool

from aira2.config import settings
from aira2 import mcp_payloads
from aira2.rag import search_runbooks

logger = logging.getLogger("aira2.tools")


@tool
def search_runbook(query: str) -> str:
    """Search incident runbooks by meaning, not keywords. Use the incident title and error text."""
    hits = search_runbooks(query, limit=3)
    if not hits:
        return "No runbooks retrieved."
    parts = []
    for hit in hits:
        parts.append(f"{hit['title']} (score {hit['score']:.2f})\n{hit['content']}")
    return "\n\n".join(parts)


@tool
def get_service_health(service: str) -> str:
    """Read-only: return simulated health for a service such as payments-api."""
    payload = mcp_payloads.get_service_health(service)
    logger.info("MCP get_service_health(%s)", service)
    return json.dumps(payload)


@tool
def get_recent_errors(service: str) -> str:
    """Read-only: return simulated recent HTTP errors for a service."""
    payload = mcp_payloads.get_recent_errors(service)
    logger.info("MCP get_recent_errors(%s)", service)
    return json.dumps(payload)


@tool
def get_recent_deployments(service: str) -> str:
    """Read-only: return simulated recent deployments for a service."""
    payload = mcp_payloads.get_recent_deployments(service)
    return json.dumps(payload)


@tool
def get_container_status(service: str) -> str:
    """Read-only: return simulated container status."""
    payload = mcp_payloads.get_container_status(service)
    return json.dumps(payload)


def optional_web_search_tool():
    """Return the Tavily tool only when TAVILY_API_KEY is set.

    Course: notebooks/module-1/1.2_web_search.ipynb
    AIRA1 did not search the web. This is extra context, never required.
    """
    if not settings.tavily_api_key or "your_tavily" in settings.tavily_api_key:
        return None
    try:
        from langchain_tavily import TavilySearch

        return TavilySearch(max_results=3, name="search_web")
    except Exception as exc:  # pragma: no cover - optional dependency path
        logger.warning("Tavily tool not available: %s", exc)
        return None


def mcp_tools() -> list:
    """Tools the Act step is allowed to call."""
    tools = [get_service_health, get_recent_errors, get_recent_deployments, get_container_status]
    web = optional_web_search_tool()
    if web is not None:
        tools.append(web)
    return tools
