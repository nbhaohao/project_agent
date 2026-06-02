"""memory tools — remember/recall with fake embedder + fake repo."""

import uuid

from app.application.agent.tools.memory import build_memory_tools
from app.domain.memory import Memory


class FakeEmbedder:
    """Returns a fixed 1024-dim vector so tests are deterministic."""
    def __init__(self, vector: list[float] | None = None) -> None:
        self._vec = vector or [0.1] * 1024

    async def embed(self, text: str) -> list[float]:
        return self._vec


class FakeMemoryRepo:
    def __init__(self) -> None:
        self._store: list[tuple[Memory, list[float]]] = []

    async def add(self, memory: Memory, embedding: list[float]) -> None:
        self._store.append((memory, embedding))

    async def search(self, embedding: list[float], top_k: int = 5) -> list[Memory]:
        return [m for m, _ in self._store[:top_k]]


async def test_remember_stores_memory():
    repo = FakeMemoryRepo()
    remember, _ = build_memory_tools(FakeEmbedder(), repo)

    result = await remember.handler({"text": "the sky is blue"})

    assert "Remembered" in result
    assert len(repo._store) == 1
    assert repo._store[0][0].content == "the sky is blue"


async def test_remember_embeds_text():
    repo = FakeMemoryRepo()
    embedder = FakeEmbedder(vector=[0.42] * 1024)
    remember, _ = build_memory_tools(embedder, repo)

    await remember.handler({"text": "hello"})

    stored_embedding = repo._store[0][1]
    assert stored_embedding == [0.42] * 1024


async def test_recall_returns_formatted_results():
    repo = FakeMemoryRepo()
    remember, recall = build_memory_tools(FakeEmbedder(), repo)

    await remember.handler({"text": "Paris is the capital of France"})
    await remember.handler({"text": "The Eiffel Tower is in Paris"})

    result = await recall.handler({"query": "France capital"})

    assert "Paris is the capital of France" in result
    assert result.startswith("-")


async def test_recall_empty_repo_returns_no_memories_message():
    _, recall = build_memory_tools(FakeEmbedder(), FakeMemoryRepo())

    result = await recall.handler({"query": "anything"})

    assert result == "No relevant memories found."


async def test_recall_respects_top_k():
    repo = FakeMemoryRepo()
    remember, recall = build_memory_tools(FakeEmbedder(), repo)

    for i in range(5):
        await remember.handler({"text": f"fact {i}"})

    result = await recall.handler({"query": "fact", "top_k": 2})
    lines = [l for l in result.splitlines() if l.strip()]
    assert len(lines) == 2
