"""Allow:  python -m aira2

Opens http://127.0.0.1:5080  (stop the C# Aira.Api first — same port).
"""

import uvicorn

from aira2.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "aira2.app:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
