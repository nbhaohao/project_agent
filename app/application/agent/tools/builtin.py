"""Built-in tools shipped with the runtime."""

from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.application.agent.tools.base import Tool, ToolRegistry
from app.config import settings

_FETCH_MAX_CHARS = 8_000


async def _get_current_time(inp: dict) -> str:
    return datetime.now(UTC).isoformat()


async def _http_fetch(inp: dict) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.get(inp["url"], follow_redirects=True, timeout=10)
        r.raise_for_status()
        return r.text[:_FETCH_MAX_CHARS]


async def _file_read(inp: dict) -> str:
    root = Path(settings.tool_fs_root).resolve()
    target = (root / inp["path"]).resolve()
    if not target.is_relative_to(root):
        raise PermissionError(f"path traversal denied: {inp['path']!r}")
    return target.read_text()


GET_CURRENT_TIME = Tool(
    name="get_current_time",
    description="Returns the current UTC date and time as an ISO-8601 string.",
    input_schema={"type": "object", "properties": {}, "required": []},
    handler=_get_current_time,
)

HTTP_FETCH = Tool(
    name="http_fetch",
    description="Fetches the text content of a URL. Returns up to 8 000 characters.",
    input_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch."},
        },
        "required": ["url"],
    },
    handler=_http_fetch,
    capability="network",
    timeout=15.0,
)

FILE_READ = Tool(
    name="file_read",
    description="Reads a file under the allowed filesystem root. Path must be relative.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path from the filesystem root."},
        },
        "required": ["path"],
    },
    handler=_file_read,
    capability="fs_read",
    timeout=5.0,
)


def build_registry(allowed: set[str] | None = None) -> ToolRegistry:
    reg = ToolRegistry(allowed=allowed or set())
    reg.register(GET_CURRENT_TIME)
    reg.register(HTTP_FETCH)
    reg.register(FILE_READ)
    return reg
