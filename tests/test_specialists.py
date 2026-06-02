"""Specialist definitions — verify policy configuration, not the mechanism."""

from app.application.agent.specialists import RESEARCHER, SUMMARIZER, build_subagent_tools
from app.application.agent.subagent import SubAgentDefinition


class _FakeLLM:
    async def complete(self, messages, tools, system=""):
        pass


class _FakeEmbedder:
    async def embed(self, text):
        return [0.0] * 1024


class _FakeMemoryRepo:
    async def add(self, memory, embedding): pass
    async def search(self, embedding, top_k=5): return []


def test_researcher_definition():
    assert isinstance(RESEARCHER, SubAgentDefinition)
    assert RESEARCHER.name == "researcher"
    assert "network" in RESEARCHER.capabilities
    assert "http_fetch" in RESEARCHER.system_prompt.lower() or "web" in RESEARCHER.system_prompt.lower()


def test_summarizer_definition():
    assert isinstance(SUMMARIZER, SubAgentDefinition)
    assert SUMMARIZER.name == "summarizer"
    assert SUMMARIZER.capabilities == set()  # no network


def test_build_subagent_tools_returns_two_tools():
    tools = build_subagent_tools(
        llm=_FakeLLM(), embedder=_FakeEmbedder(), memory_repo=_FakeMemoryRepo()
    )
    assert len(tools) == 2
    names = {t.name for t in tools}
    assert names == {"delegate_to_researcher", "delegate_to_summarizer"}


def test_all_specialist_tools_have_long_timeout():
    tools = build_subagent_tools(
        llm=_FakeLLM(), embedder=_FakeEmbedder(), memory_repo=_FakeMemoryRepo()
    )
    for tool in tools:
        assert tool.timeout >= 120.0, f"{tool.name} timeout too short: {tool.timeout}"
