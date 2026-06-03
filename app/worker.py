"""Worker entrypoint — consumes runs from Redis queue and executes them.

Run as a separate process:
    uv run python -m app.worker
"""

import asyncio
import contextlib
import logging
import signal
import uuid
from collections.abc import Awaitable

from app.application.agent.events import derive_events
from app.observability.tracing import bind_trace, configure_logging
from app.application.agent.loop import AgentLoop
from app.application.agent.specialists import build_subagent_tools
from app.application.agent.tools.builtin import build_registry
from app.application.agent.tools.memory import build_memory_tools
from app.domain.message import RunMessage
from app.domain.run import RunCancelled, RunStatus
from app.infrastructure.cancel import RedisCancelSignal
from app.infrastructure.db import SessionLocal
from app.infrastructure.embedder import SiliconFlowEmbedder
from app.infrastructure.event_bus import RedisEventBus
from app.config import settings
from app.infrastructure.llm import AnthropicLLMClient, MeteredLLMClient
from app.infrastructure.queue import RedisRunQueue
from app.infrastructure.redis import redis_client
from app.infrastructure.repositories import (
    SqlAlchemyMemoryRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyRunRepository,
)

logger = logging.getLogger(__name__)


def _normalize_content(content: object) -> list[dict]:
    """Convert Anthropic SDK block objects (or dicts) to plain dicts for storage."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    result = []
    for block in content:  # type: ignore[union-attr]
        if isinstance(block, dict):
            result.append(block)
        elif hasattr(block, "model_dump"):
            result.append(block.model_dump())
        else:
            result.append({"type": getattr(block, "type", "unknown")})
    return result


def _make_on_message(run_id: uuid.UUID, event_bus: RedisEventBus):
    """Return an async callback that persists each message and publishes events."""
    seq = 0

    async def on_message(role: str, content: object) -> None:
        nonlocal seq
        content_dicts = _normalize_content(content)

        msg = RunMessage.create(run_id=run_id, seq=seq, role=role, content=content_dicts)
        async with SessionLocal() as session, session.begin():
            await SqlAlchemyMessageRepository(session).add(msg)

        for event in derive_events(msg):
            await event_bus.publish(run_id, event)

        seq += 1

    return on_message


def _build_loop() -> tuple[AgentLoop, MeteredLLMClient]:
    metered = MeteredLLMClient(AnthropicLLMClient())
    embedder = SiliconFlowEmbedder()
    memory_repo = SqlAlchemyMemoryRepository()

    registry = build_registry(allowed={"network", "fs_read"})
    for tool in build_memory_tools(embedder, memory_repo):
        registry.register(tool)
    for tool in build_subagent_tools(llm=metered, embedder=embedder, memory_repo=memory_repo):
        registry.register(tool)

    return AgentLoop(llm=metered, registry=registry), metered


async def _run_cancellable(
    coro: Awaitable[str],
    cancel_signal: RedisCancelSignal,
    run_id: uuid.UUID,
    *,
    poll_interval: float = 0.5,
) -> str:
    """Run coro as a Task; watchdog cancels it when the cancel signal fires.

    Reduces cancel latency from "wait for next loop iteration" to ~poll_interval,
    allowing mid-LLM-call interruption.
    """
    task: asyncio.Task[str] = asyncio.create_task(coro)  # type: ignore[arg-type]

    async def _watchdog() -> None:
        while True:
            await asyncio.sleep(poll_interval)
            if task.done():
                return
            if await cancel_signal.is_requested(run_id):
                task.cancel()
                return

    watchdog = asyncio.create_task(_watchdog())
    try:
        return await task
    except (asyncio.CancelledError, RunCancelled):
        raise RunCancelled("run was cancelled")
    finally:
        watchdog.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watchdog


async def _process_one(
    run_id: uuid.UUID,
    event_bus: RedisEventBus,
    cancel_signal: RedisCancelSignal,
) -> None:
    bind_trace(run_id)
    async with SessionLocal() as session, session.begin():
        repo = SqlAlchemyRunRepository(session)
        run = await repo.get(run_id)
        if run is None:
            logger.warning("run %s not found, skipping", run_id)
            return
        if run.status is not RunStatus.QUEUED:
            # Cancelled while waiting in queue — DB already updated by API, just skip
            logger.info("run %s status=%s on dequeue, skipping", run_id, run.status)
            return
        run.mark_running()
        await repo.update(run)
        saved_input = run.input

    on_message = _make_on_message(run_id, event_bus)

    async def should_cancel() -> bool:
        return await cancel_signal.is_requested(run_id)

    loop, metered = _build_loop()
    result: str | None = None
    error: str | None = None
    cancelled = False
    try:
        result = await _run_cancellable(
            loop.run(saved_input, on_message=on_message, should_cancel=should_cancel),
            cancel_signal,
            run_id,
        )
    except RunCancelled:
        logger.info("run %s cancelled mid-execution", run_id)
        cancelled = True
    except Exception as exc:
        logger.exception("agent failed for run %s", run_id)
        error = str(exc)

    async with SessionLocal() as session, session.begin():
        repo = SqlAlchemyRunRepository(session)
        run = await repo.get(run_id)
        if run is None:
            return
        if cancelled:
            run.mark_cancelled()
        elif error is None:
            run.mark_succeeded(result)
        else:
            run.mark_failed(error)
        run.record_metrics(metered.metrics, settings.model_id)
        await repo.update(run)

    if cancelled:
        await event_bus.publish(run_id, {"type": "cancelled"})
    elif error is None:
        await event_bus.publish(run_id, {
            "type": "done",
            "result": result or "",
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
            "cost_usd": run.cost_usd,
            "llm_calls": run.llm_calls,
        })
    else:
        await event_bus.publish(run_id, {"type": "error", "error": error})

    terminal = "cancelled" if cancelled else ("succeeded" if error is None else "failed")
    logger.info("run %s → %s", run_id, terminal)


async def run_worker() -> None:
    queue = RedisRunQueue(redis_client)
    event_bus = RedisEventBus(redis_client)
    cancel_signal = RedisCancelSignal(redis_client)
    logger.info("worker started, waiting for runs…")
    while True:
        try:
            run_id = await queue.dequeue(timeout=5)
            if run_id is None:
                continue
            await _process_one(run_id, event_bus, cancel_signal)
        except Exception:
            logger.exception("unexpected error in worker loop, continuing")


def main() -> None:
    configure_logging()

    loop = asyncio.new_event_loop()

    def _shutdown(*_):
        logger.info("shutdown signal received")
        loop.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown)

    try:
        loop.run_until_complete(run_worker())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
