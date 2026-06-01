"""Worker entrypoint — consumes runs from Redis queue and executes them.

Run as a separate process:
    python -m app.worker

M2: agent is a stub (sleep + echo). Real LLM loop comes in M3.
"""

import asyncio
import logging
import signal

from app.infrastructure.db import SessionLocal
from app.infrastructure.queue import RedisRunQueue
from app.infrastructure.redis import redis_client
from app.infrastructure.repositories import SqlAlchemyRunRepository

logger = logging.getLogger(__name__)


async def _fake_agent(input: str) -> None:
    """Stub — simulates agent work without calling an LLM."""
    logger.info("agent stub running for input=%r", input)
    await asyncio.sleep(2)


async def _process_one(run_id, queue: RedisRunQueue) -> None:
    async with SessionLocal() as session, session.begin():
        repo = SqlAlchemyRunRepository(session)
        run = await repo.get(run_id)
        if run is None:
            logger.warning("run %s not found, skipping", run_id)
            return
        run.mark_running()
        await repo.update(run)
        saved_input = run.input

    try:
        await _fake_agent(saved_input)
        status = "succeeded"
    except Exception:
        logger.exception("agent failed for run %s", run_id)
        status = "failed"

    async with SessionLocal() as session, session.begin():
        repo = SqlAlchemyRunRepository(session)
        run = await repo.get(run_id)
        if run is None:
            return
        if status == "succeeded":
            run.mark_succeeded()
        else:
            run.mark_failed()
        await repo.update(run)

    logger.info("run %s → %s", run_id, status)


async def run_worker() -> None:
    queue = RedisRunQueue(redis_client)
    logger.info("worker started, waiting for runs…")
    while True:
        run_id = await queue.dequeue(timeout=5)
        if run_id is None:
            continue
        await _process_one(run_id, queue)


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
