@echo off
REM Start AIRA2. Stop the C# AIRA API first (same port 5080).
REM Start Docker Desktop + `docker compose up -d` in D:\Study\AIRA if Postgres is down.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv with the LangChain course Python 3.13...
  "D:\Study\Langchain\lca-lc-foundations\.venv\Scripts\python.exe" -m venv .venv
  if errorlevel 1 (
    echo Could not create the virtual environment. Is the course Python still at
    echo D:\Study\Langchain\lca-lc-foundations\.venv\Scripts\python.exe
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install -e .
)

".venv\Scripts\python.exe" -m aira2
