# Start AIRA2. Stop the C# AIRA API first (same port 5080).
# Start Docker Desktop + `docker compose up -d` in D:\Study\AIRA if Postgres is down.

Set-Location $PSScriptRoot
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating .venv with the LangChain course Python 3.13..."
    & "D:\Study\Langchain\lca-lc-foundations\.venv\Scripts\python.exe" -m venv .venv
    & ".\.venv\Scripts\python.exe" -m pip install -e .
}
& ".\.venv\Scripts\python.exe" -m aira2
