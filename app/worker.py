"""Worker entrypoint — consumes runs from Redis queue and executes them.

Run as a separate process:
    uv run python -m app.worker
"""

import asyncio
import logging
import signal

from app.application.agent.loop import AgentLoop
from app.application.agent.tools.builtin import build_registry
from app.infrastructure.db import SessionLocal
from app.infrastructure.llm import AnthropicLLMClient
from app.infrastructure.queue import RedisRunQueue
from app.infrastructure.redis import redis_client
from app.infrastructure.repositories import SqlAlchemyRunRepository

logger = logging.getLogger(__name__)


def _build_loop() -> AgentLoop:
    return AgentLoop(
        llm=AnthropicLLMClient(),
        registry=build_registry(allowed={"network", "fs_read"}),
    )


async def _process_one(run_id) -> None:
    async with SessionLocal() as session, session.begin():
        repo = SqlAlchemyRunRepository(session)
        run = await repo.get(run_id)
        if run is None:
            logger.warning("run %s not found, skipping", run_id)
            return
        run.mark_running()
        await repo.update(run)
        saved_input = run.input

    result: str | None = None
    error: str | None = None
    try:
        result = await _build_loop().run(saved_input)
    except Exception as exc:
        logger.exception("agent failed for run %s", run_id)
        error = str(exc)

    async with SessionLocal() as session, session.begin():
        repo = SqlAlchemyRunRepository(session)
        run = await repo.get(run_id)
        if run is None:
            return
        if error is None:
            run.mark_succeeded(result)
        else:
            run.mark_failed(error)
        await repo.update(run)

    logger.info("run %s → %s", run_id, "succeeded" if error is None else "failed")


async def run_worker() -> None:
    queue = RedisRunQueue(redis_client)
    logger.info("worker started, waiting for runs…")
    while True:
        run_id = await queue.dequeue(timeout=5)
        if run_id is None:
            continue
        await _process_one(run_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

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
