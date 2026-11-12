"""Run the MCP server over stdio (feature 006, task T030; contracts/mcp-tools.md).

    PAKTAX_TOKEN=ptx_… docker compose exec -T -e PAKTAX_TOKEN backend python -m app.mcp_server

The token comes only from the environment, never from a file in the repo; a missing or invalid
token makes every tool call fail with "invalid or expired token". stdout carries the MCP
protocol, so anything else goes to stderr.
"""

import os

from app.db import get_sessionmaker
from app.mcp_server.server import build_server
from app.rag.embed import GeminiEmbedder
from app.settings import get_settings


def main() -> None:
    """Serve the three tools on stdin/stdout until the client disconnects."""
    server = build_server(
        os.environ.get("PAKTAX_TOKEN", "").strip() or None,
        get_sessionmaker(),
        GeminiEmbedder(api_key=get_settings().gemini_api_key, attempts=1),
    )
    server.run("stdio")


if __name__ == "__main__":
    main()
