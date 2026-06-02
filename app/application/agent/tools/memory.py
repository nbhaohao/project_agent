"""Memory tools — remember and recall, backed by Embedder + MemoryRepository ports."""

from app.application.ports import Embedder, MemoryRepository
from app.domain.memory import Memory

from .base import Tool


def build_memory_tools(embedder: Embedder, repo: MemoryRepository) -> list[Tool]:
    async def _remember(tool_input: dict) -> str:
        text = tool_input["text"]
        embedding = await embedder.embed(text)
        await repo.add(Memory.create(text), embedding)
        return f"Remembered: {text[:120]}"

    async def _recall(tool_input: dict) -> str:
        query = tool_input["query"]
        top_k = int(tool_input.get("top_k", 5))
        embedding = await embedder.embed(query)
        memories = await repo.search(embedding, top_k=top_k)
        if not memories:
            return "No relevant memories found."
        return "\n".join(f"- {m.content}" for m in memories)

    return [
        Tool(
            name="remember",
            description=(
                "Save a piece of information to long-term memory so it can be recalled "
                "in future runs."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The information to remember."},
                },
                "required": ["text"],
            },
            handler=_remember,
            timeout=15.0,
        ),
        Tool(
            name="recall",
            description=(
                "Search long-term memory for information relevant to a query. "
                "Returns the most semantically similar stored memories."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for."},
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 5).",
                    },
                },
                "required": ["query"],
            },
            handler=_recall,
            timeout=15.0,
        ),
    ]
