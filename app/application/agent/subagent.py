"""Sub-agent mechanism — wrap a nested AgentLoop as a Tool.

Each sub-agent is defined by a SubAgentDefinition (name, system prompt,
capability set). build_subagent_tool() wraps it into a Tool whose handler
spins up a fresh AgentLoop and runs it to completion, returning the final
text result to the parent agent as a tool_result string (black-box mode).

Recursion depth is fixed at 1: the sub-agent's registry contains builtins
and memory tools but NOT other sub-agent tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.application.agent.loop import AgentLoop
from app.application.agent.tools.base import Tool
from app.application.agent.tools.builtin import build_registry
from app.application.agent.tools.memory import build_memory_tools

if TYPE_CHECKING:
    from app.application.ports import Embedder, LLMClient, MemoryRepository


@dataclass
class SubAgentDefinition:
    name: str
    description: str
    system_prompt: str
    capabilities: set[str] = field(default_factory=set)


def build_subagent_tool(
    definition: SubAgentDefinition,
    *,
    llm: LLMClient,
    embedder: Embedder,
    memory_repo: MemoryRepository,
) -> Tool:
    """Return a Tool that delegates a task to a nested AgentLoop."""

    async def _handler(tool_input: dict) -> str:
        task = tool_input["task"]
        registry = build_registry(allowed=definition.capabilities)
        for tool in build_memory_tools(embedder, memory_repo):
            registry.register(tool)
        loop = AgentLoop(llm=llm, registry=registry)
        return await loop.run(task, system=definition.system_prompt)

    return Tool(
        name=f"delegate_to_{definition.name}",
        description=definition.description,
        input_schema={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task to delegate to this agent.",
                },
            },
            "required": ["task"],
        },
        handler=_handler,
        timeout=120.0,
    )
