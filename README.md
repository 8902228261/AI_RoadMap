# AIRA2

Python + LangChain remake of AIRA. Same incident workflow, same
Postgres database, same dashboard. The C# agent loop is now a LangGraph.

**Read this first if you are new to Python:** [docs/LEARNING-GUIDE.md](docs/LEARNING-GUIDE.md)

## Quick start

1. Start Postgres (`docker compose up -d` in `D:\Study\AIRA`).
2. Stop the C# **AIRA API** if it is running (both use port 5080).
3. Confirm `OPENAI_API_KEY` is in `D:\Study\Langchain\lca-lc-foundations\.env`.
4. In this folder:

```powershell
cd D:\Study\AIRA2
.\run.cmd
```

If PowerShell blocks `.\run.ps1`, use `.\run.cmd` instead. You can also start it without any script:

```powershell
cd D:\Study\AIRA2
.\.venv\Scripts\python.exe -m aira2
```

5. Open http://127.0.0.1:5080 → Seed INC-001 → Start investigation.

Debug: open this folder in Cursor, set breakpoints in `aira2/agent_graph.py`,
press F5 on **AIRA2 API**. Details are in the learning guide.
