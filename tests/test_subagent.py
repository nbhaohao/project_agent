"""SubAgent mechanism — fake LLM/embedder/repo, no real infra."""

from dataclasses import dataclass, field

from app.application.agent.subagent import SubAgentDefinition, build_subagent_tool


# ── fakes ─────────────────────────────────────────────────────────────────────

@dataclass
class FakeBlock:
    type: str
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict = field(default_factory=dict)


@dataclass
class FakeResponse:
    content: list
    stop_reason: str


class FakeLLM:
    def __init__(self, text: str) -> None:
        self._text = text

    async def complete(self, messages, tools, system=""):
        return FakeResponse(
            content=[FakeBlock("text", text=self._text)],
            stop_reason="end_turn",
        )


class FakeEmbedder:
    async def embed(self, text: str) -> list[float]:
        return [0.0] * 1024


class FakeMemoryRepo:
    async def add(self, memory, embedding) -> None:
        pass

    async def search(self, embedding, top_k=5):
        return []


# ── tests ─────────────────────────────────────────────────────────────────────

async def test_subagent_tool_name_matches_definition():
    defn = SubAgentDefinition(
        name="researcher",
        description="Does research.",
        system_prompt="You are a researcher.",
        capabilities={"network"},
    )
    tool = build_subagent_tool(defn, llm=FakeLLM("result"), embedder=FakeEmbedder(), memory_repo=FakeMemoryRepo())

    assert tool.name == "delegate_to_researcher"
    assert tool.timeout == 120.0


async def test_subagent_handler_returns_subloop_result():
    defn = SubAgentDefinition(
        name="summarizer",
        description="Summarises text.",
        system_prompt="You are a summarizer.",
    )
    tool = build_subagent_tool(
        defn,
        llm=FakeLLM("Here is the summary."),
        embedder=FakeEmbedder(),
        memory_repo=FakeMemoryRepo(),
    )

    result = await tool.handler({"task": "Summarise this document."})

    assert result == "Here is the summary."


async def test_subagent_system_prompt_passed_to_loop():
    received_systems: list[str] = []

    class CapturingLLM:
        async def complete(self, messages, tools, system=""):
            received_systems.append(system)
            return FakeResponse([FakeBlock("text", text="done")], "end_turn")

    defn = SubAgentDefinition(
        name="expert",
        description="An expert.",
        system_prompt="You are a domain expert.",
    )
    tool = build_subagent_tool(
        defn,
        llm=CapturingLLM(),
        embedder=FakeEmbedder(),
        memory_repo=FakeMemoryRepo(),
    )
    await tool.handler({"task": "do something"})

    assert received_systems == ["You are a domain expert."]


async def test_subagent_capability_filtering():
    """Sub-agent with no capabilities should not expose http_fetch."""
    seen_tool_names: list[list[str]] = []

    class CapturingLLM:
        async def complete(self, messages, tools, system=""):
            seen_tool_names.append([t["name"] for t in tools])
            return FakeResponse([FakeBlock("text", text="done")], "end_turn")

    defn = SubAgentDefinition(
        name="no_network",
        description="No network access.",
        system_prompt="",
        capabilities=set(),  # no network
    )
    tool = build_subagent_tool(
        defn, llm=CapturingLLM(), embedder=FakeEmbedder(), memory_repo=FakeMemoryRepo()
    )
    await tool.handler({"task": "think only"})

    assert seen_tool_names, "LLM should have been called"
    tool_names = seen_tool_names[0]
    assert "http_fetch" not in tool_names   # network capability filtered out
    assert "get_current_time" in tool_names  # no capability = always visible
    assert "remember" in tool_names
    assert "recall" in tool_names
