# Temporary re-exports so M3 imports still work — removed in M4(3/4)
from datetime import UTC, datetime

TOOLS_SCHEMA: list[dict] = [
    {
        "name": "get_current_time",
        "description": "Returns the current UTC date and time as an ISO-8601 string.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    }
]


def dispatch_tool(name: str, tool_input: dict) -> str:
    if name == "get_current_time":
        return datetime.now(UTC).isoformat()
    raise ValueError(f"unknown tool: {name!r}")
