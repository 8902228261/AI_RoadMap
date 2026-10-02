"""RAG (Retrieval Augmented Generation) for runbooks.

This follows LangChain Academy Module 2 bonus_rag.ipynb:
  OpenAIEmbeddings → InMemoryVectorStore → similarity_search

Why not reuse knowledge_chunks.embedding?
  C# AIRA stored nomic-embed-text vectors (768 numbers).
  AIRA2 uses OpenAI embeddings (1536 numbers). Those spaces cannot be mixed.
  We still reuse the *text* of the runbooks from that table.
"""

from __future__ import annotations

import logging

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

from aira2.config import settings
from aira2.database import get_connection
from aira2.repository import load_runbook_rows

logger = logging.getLogger("aira2.rag")

# Same three runbooks as C# RunbookSeeder. Used only if the table is empty.
FALLBACK_RUNBOOKS: list[tuple[str, str]] = [
    (
        "Payment Gateway Runbook",
        """
Use this runbook when checkout or payment APIs return 401 or 403.
1. Call application/get_service_health for payments-api.
2. Call application/get_recent_errors and look for gateway credential rejection.
3. Identify an authentication failure against the payment gateway.
4. Propose a credential recovery action. Do not rotate production secrets automatically.
""".strip(),
    ),
    (
        "Container Crash Runbook",
        """
Use this runbook when a service is unhealthy or a container has stopped.
1. Inspect container status with infrastructure/get_container_status.
2. Read recent logs.
3. Restart requires human approval in production.
""".strip(),
    ),
    (
        "Bad Deployment Runbook",
        """
Use this runbook when errors start immediately after a deployment.
1. Compare the deployment timeline with the first error timestamp.
2. Inspect recent errors.
3. Recommend rollback or escalation rather than restarting at random.
""".strip(),
    ),
]

# Built once at startup. Module-level so tools.py can search it.
vector_store: InMemoryVectorStore | None = None


def build_vector_store() -> InMemoryVectorStore:
    """Embed runbook text with OpenAI and keep it in RAM for this process."""
    global vector_store
    settings.require_openai()

    embeddings = OpenAIEmbeddings(model=settings.embedding_model)

    with get_connection() as conn:
        rows = load_runbook_rows(conn)

    if not rows:
        logger.warning("knowledge_chunks is empty. Using the same 3 fallback runbooks as C# AIRA.")
        rows = FALLBACK_RUNBOOKS
    else:
        logger.info("Loaded %s runbook(s) from knowledge_chunks.", len(rows))

    documents = [
        Document(page_content=content, metadata={"title": title, "source": "runbook"})
        for title, content in rows
    ]
    store = InMemoryVectorStore(embeddings)
    store.add_documents(documents)
    vector_store = store
    return store


def search_runbooks(query: str, limit: int = 3) -> list[dict]:
    """Return the closest runbooks. Higher score = more similar."""
    if vector_store is None:
        raise RuntimeError("Vector store is not ready. Did startup finish?")

    # similarity_search_with_score returns (Document, distance).
    # For OpenAI embeddings the score is a distance: smaller is closer.
    pairs = vector_store.similarity_search_with_score(query, k=limit)
    results: list[dict] = []
    for document, distance in pairs:
        results.append(
            {
                "title": document.metadata.get("title", "runbook"),
                "content": document.page_content,
                "score": 1.0 - float(distance) if distance <= 1 else 1.0 / (1.0 + float(distance)),
            }
        )
    return results
