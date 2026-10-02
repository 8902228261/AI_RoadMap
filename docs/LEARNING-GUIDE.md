# AIRA2 learning guide

This is the Python + LangChain remake of the .NET AIRA project you already
debugged. The product is the same. The libraries are the ones from
**LangChain Academy — Foundation: Introduction to LangChain**.

Course repo you followed: `D:\Study\Langchain\lca-lc-foundations`

---

## 1. What stays the same vs what changed

| Piece | AIRA (.NET) | AIRA2 (Python) |
|---|---|---|
| Database | Postgres `aira` | **Same** database and tables |
| UI | `D:\Study\AIRA\ui\aira-dashboard` | **Same** folder, served by FastAPI |
| Workflow | Retrieve → Plan → Act → Conclude | **Same** four steps |
| INC-001 | payments-api 401 | **Same** seed + simulated MCP JSON |
| Chat model | local Ollama `qwen2.5:3b` | OpenAI (`CHAT_MODEL`, default `gpt-5-nano`) |
| Embeddings | local `nomic-embed-text` (768-d) | OpenAI `text-embedding-3-small` |
| Agent code | `LocalAgentOrchestrator.cs` | `aira2/agent_graph.py` |
| HTTP API | `Aira.Api` port 5080 | FastAPI port **5080** |

Stop the C# **AIRA API** before you start AIRA2. Both want port 5080.

We do **not** write into `knowledge_chunks.embedding`. That column is 768
numbers from Ollama. OpenAI embeddings have a different size, so AIRA2
embeds runbook **text** in memory (same pattern as course `bonus_rag.ipynb`).

---

## 2. How to run

### Prerequisites

1. Docker Desktop running, then Postgres from the AIRA repo (`docker compose up -d` in `D:\Study\AIRA`).
2. The C# app has already created the tables (you have already done this).
3. OpenAI key in `D:\Study\Langchain\lca-lc-foundations\.env`.
4. Python **3.12 or 3.13** (same range as the course). Windows Store Python 3.14 will not work.
   This machine already has 3.13 inside the course venv:
   `D:\Study\Langchain\lca-lc-foundations\.venv\Scripts\python.exe`
5. pip (or [uv](https://docs.astral.sh/uv/) if you install it later).

### Install (once)

In `D:\Study\AIRA2`:

```powershell
# Use the course Python 3.13 — do not use `python` if it is 3.14
& "D:\Study\Langchain\lca-lc-foundations\.venv\Scripts\python.exe" -m venv .venv
.\.venv\Scripts\activate
python -m pip install -e .
```

Copy `.env.example` to `.env` if you do not already have `.env`.
The file already points at your course `.env` for `OPENAI_API_KEY`.

Optional: in the course `.env` set `LANGSMITH_TRACING=true` and a real
`LANGSMITH_API_KEY`. Then every graph node appears at
[https://smith.langchain.com](https://smith.langchain.com) under project `aira2`.

### Start

```powershell
# stop F5 on AIRA API first if it is still running

cd D:\Study\AIRA2
.\run.cmd
```

Windows often blocks `.ps1` files (`running scripts is disabled`). Use `run.cmd`, or start Python directly:

```powershell
cd D:\Study\AIRA2
.\.venv\Scripts\python.exe -m aira2
```

Or in Cursor: open the **AIRA2** folder → Run and Debug → **AIRA2 API**.

Browser: [http://127.0.0.1:5080](http://127.0.0.1:5080)

1. Seed INC-001
2. Start investigation
3. Wait for evidence + hypothesis (OpenAI is usually much faster than Ollama)

### Check the pieces without the UI

```powershell
curl http://127.0.0.1:5080/api/info
curl http://127.0.0.1:5080/mcp/application/get_service_health?service=payments-api
```

---

## 3. Code map (read in this order)

Think of each file as one layer. You do not need to read them all at once.

```
browser (same app.js)
    │
    ▼
aira2/app.py              HTTP routes  (/api/incidents, /mcp, /)
    │
    ▼
aira2/domain.py           In-memory rules  (status, evidence, timeline)
aira2/repository.py       SQL into the existing AIRA tables
    │
    ▼
aira2/agent_graph.py      LangGraph: retrieve → plan → act → conclude
    │
    ├── aira2/rag.py      OpenAI embeddings + InMemoryVectorStore
    ├── aira2/tools.py    @tool functions (MCP + optional Tavily)
    └── aira2/mcp_payloads.py   Fake payments-api 401 JSON
```

### What happens when you click **Start investigation**

1. `app.py` → `api_investigate`
2. `repository.get_incident` loads the row + children
3. `Incident.start_investigation` sets status `Investigating` **in memory only**
4. `agent_graph.investigate` runs the graph (OpenAI calls happen here)
5. Graph results are copied onto the incident (`add_evidence`, `add_hypothesis`)
6. `repository.save_investigation` writes one transaction
7. Dashboard GETs the incident again and draws evidence / timeline

If step 4 throws (bad API key, wrong model name), step 6 never runs.
Postgres still shows `New`. That is the same safety as C# AIRA.

### The four graph nodes

| Node | Course idea | What it does |
|---|---|---|
| `retrieve` | Module 2 `bonus_rag.ipynb` | Embed the incident text, pick top 3 runbooks |
| `plan` | Module 1 `init_chat_model` | 3-sentence plan from runbooks only |
| `act` | `create_agent` + middleware | Call `get_service_health` and `get_recent_errors` |
| `conclude` | structured output | JSON `{hypothesis, confidence, nextAction}` |

`act` uses two middlewares you saw in Module 3:

- `log_model_calls` (`@wrap_model_call`) — prints each model call
- `act_system_prompt` (`@dynamic_prompt`) — safety + which tools to call

Tavily (`search_web`) is added only if `TAVILY_API_KEY` is set. The
investigation still works without it.

---

## 4. How to debug (Python beginner)

### A. Debugger (best)

1. File → Open Folder → `D:\Study\AIRA2`
2. Install the **Python** and **Python Debugger** extensions if asked
3. Open `aira2/agent_graph.py`
4. Click left of the line number on `def retrieve_node` (red dot)
5. Also set a breakpoint on `def api_investigate` in `app.py`
6. Run **AIRA2 API** (F5)
7. In the browser click Seed, then Start investigation
8. Cursor stops on the breakpoint. Use:

   - **F10** Step over — run the current line
   - **F11** Step into — go inside a function
   - **Variables** panel — look at `incident`, `state`, `runbooks`

Suggested breakpoint tour:

1. `app.py` `api_investigate` — see the GUID from the URL
2. `domain.py` `start_investigation` — status becomes Investigating
3. `agent_graph.py` `retrieve_node` — runbook list
4. `agent_graph.py` `plan_node` — OpenAI plan text
5. `agent_graph.py` `act_node` — tool messages after `create_agent`
6. `agent_graph.py` `conclude_node` — hypothesis
7. `repository.py` `save_investigation` — SQL is about to run

### B. Logs

The terminal that started uvicorn prints lines like:

```
aira2.agent: RAG query: Payment gateway...
aira2.agent: Plan: ...
aira2.tools: MCP get_service_health(payments-api)
aira2.agent: AIRA2 finished INC-...
```

### C. LangSmith (course tracing)

If `LANGSMITH_TRACING=true` in the course `.env`:

1. Open [smith.langchain.com](https://smith.langchain.com)
2. Project `aira2` (or `LANGSMITH_PROJECT`)
3. Open the latest run
4. You should see nodes `retrieve`, `plan`, `act`, `conclude`
5. Inside `act` you will see tool calls — that is LangGraph under `create_agent`

### D. Database (DBeaver)

Same connection as AIRA: `localhost:5432` / db `aira` / user `aira` / password `aira`

After a successful investigate you should see new rows in:

- `incidents` — `Status` = `Investigating`, `CurrentPlan` filled
- `incident_evidence` — `Source` values `rag`, `llm`, `mcp:application/get_service_health`
- `incident_hypotheses` — one statement + confidence
- `incident_timeline` — Created / StatusChanged / EvidenceAdded / ...
- `incident_tool_executions` — health + errors

Column names are mixed-case (`"Id"`, `"Status"`). That is how EF Core created them.

### E. Common errors

| Symptom | Likely cause | Fix |
|---|---|---|
| `api offline` | AIRA2 not running, or C# still bound to 5080 | Stop Aira.Api, start `python -m aira2` |
| `OPENAI_API_KEY is missing` | Course `.env` not loaded | Check `COURSE_ENV_PATH` in AIRA2 `.env` |
| Model 404 / not found | Account has no `gpt-5-nano` | Set `CHAT_MODEL=gpt-4o-mini` in AIRA2 `.env` |
| `connection refused` port 5432 | Postgres down | `docker compose up -d` in AIRA |
| `column id does not exist` | SQL forgot quotes | Keep `"Id"` not `id` |
| Seed works, investigate hangs | Waiting on OpenAI | Watch the terminal; first call can take ~20s |
| UI shows old C# evidence | You are looking at an old incident | Seed a **new** INC-001 |

---

## 5. Course notebook → AIRA2 file

| Academy notebook | AIRA2 |
|---|---|
| `1.1_foundational_models.ipynb` (`init_chat_model`, `create_agent`) | `agent_graph.py` `plan_node` / `act_node` |
| `1.2_tools.ipynb` (`@tool`) | `tools.py` |
| `1.2_web_search.ipynb` (Tavily) | `tools.optional_web_search_tool` |
| `bonus_rag.ipynb` (embeddings + InMemoryVectorStore) | `rag.py` |
| `2.1_mcp.ipynb` | `/mcp/...` in `app.py` + tools in `tools.py` |
| `3.2_managing_messages.ipynb` / `3.4_*` middleware | `log_model_calls`, `act_system_prompt` |
| LangSmith tracing | set `LANGSMITH_TRACING=true` |

Official docs the course points at:

- Agents: https://docs.langchain.com/oss/python/langchain/agents
- Middleware: https://docs.langchain.com/oss/python/langchain/middleware
- LangGraph: https://docs.langchain.com/oss/python/langgraph/overview
- LangSmith: https://docs.langchain.com/langsmith/home

---

## 6. Why this is still one agent, not multi-agent

`create_agent` is **one** agent that can call tools. LangGraph here is a
**pipeline** of four steps, not four people arguing.

Module 2 `2.3_multi_agent.ipynb` would be a later upgrade (for example
Investigator + Approver). AIRA2 does not do that yet, on purpose — it
matches AIRA's first vertical slice.
