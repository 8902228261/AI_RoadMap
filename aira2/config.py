"""Load settings for AIRA2.

Python beginners: this file is the single place that reads environment
variables. Other modules import `settings` instead of calling os.getenv
everywhere.

Key loading order (later files win):
1. D:\\Study\\Langchain\\lca-lc-foundations\\.env  → OPENAI_API_KEY, TAVILY_API_KEY, LangSmith
2. AIRA2\\.env                                    → database URL, model names, port
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Folder that contains this file: .../AIRA2/aira2
PACKAGE_DIR = Path(__file__).resolve().parent
# Folder that contains pyproject.toml: .../AIRA2
PROJECT_DIR = PACKAGE_DIR.parent

# Default location of the course keys the user already created.
DEFAULT_COURSE_ENV = Path(r"D:\Study\Langchain\lca-lc-foundations\.env")


def _load_env_files() -> None:
    """Read .env files into os.environ. Does not print secret values."""
    # Allow AIRA2/.env to point at a different course file first.
    local_env = PROJECT_DIR / ".env"
    if local_env.exists():
        load_dotenv(local_env, override=False)

    course_env = Path(os.getenv("COURSE_ENV_PATH", DEFAULT_COURSE_ENV))
    if course_env.exists():
        # Course file has the OpenAI key. override=False keeps a local override.
        load_dotenv(course_env, override=False)

    # Read AIRA2/.env again so DATABASE_URL / CHAT_MODEL win over the course file.
    if local_env.exists():
        load_dotenv(local_env, override=True)


_load_env_files()


class Settings:
    """Typed bag of config. Change values in .env, not in code."""

    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://aira:aira@localhost:5432/aira"
    )
    ui_path: Path = Path(
        os.getenv("AIRA_UI_PATH", r"D:\Study\AIRA\ui\aira-dashboard")
    )
    chat_model: str = os.getenv("CHAT_MODEL", "gpt-5-nano")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    host: str = os.getenv("AIRA2_HOST", "127.0.0.1")
    port: int = int(os.getenv("AIRA2_PORT", "5080"))
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    tavily_api_key: str | None = os.getenv("TAVILY_API_KEY")
    langsmith_tracing: bool = os.getenv("LANGSMITH_TRACING", "").lower() == "true"

    def require_openai(self) -> None:
        if not self.openai_api_key or "your_openai" in self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. Put it in "
                r"D:\Study\Langchain\lca-lc-foundations\.env"
            )


settings = Settings()
