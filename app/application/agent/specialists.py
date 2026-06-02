"""Named specialist sub-agents — policy layer on top of the subagent mechanism.

Each specialist is a SubAgentDefinition that gets wrapped into a Tool by
build_subagent_tool(). The parent agent's LLM picks which specialist to
delegate to based on the task and the tool descriptions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.agent.subagent import SubAgentDefinition, build_subagent_tool
from app.application.agent.tools.base import Tool

if TYPE_CHECKING:
    from app.application.ports import Embedder, LLMClient, MemoryRepository


RESEARCHER = SubAgentDefinition(
    name="researcher",
    description=(
        "A research agent that can fetch content from URLs. "
        "Delegate tasks that require browsing the web or retrieving online information."
    ),
    system_prompt=(
        "You are a research assistant. Your job is to gather information from the web "
        "and return a clear, accurate summary of your findings. "
        "Use the http_fetch tool to retrieve content from URLs."
    ),
    capabilities={"network"},
)

SUMMARIZER = SubAgentDefinition(
    name="summarizer",
    description=(
        "A summarization agent that distills text into concise insights. "
        "Delegate tasks that require synthesizing or condensing provided information. "
        "Does not have web access — provide the raw content in the task."
    ),
    system_prompt=(
        "You are a summarization expert. "
        "Read the provided text carefully and produce a clear, concise summary "
        "that captures the key points and conclusions."
    ),
    capabilities=set(),  # text-only; no network
)

_SPECIALISTS = (RESEARCHER, SUMMARIZER)


def build_subagent_tools(
    *,
    llm: LLMClient,
    embedder: Embedder,
    memory_repo: MemoryRepository,
) -> list[Tool]:
    return [
        build_subagent_tool(defn, llm=llm, embedder=embedder, memory_repo=memory_repo)
        for defn in _SPECIALISTS
    ]
