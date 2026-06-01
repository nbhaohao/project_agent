"""Run domain — submit factory produces a well-formed QUEUED run with a uuid7 id."""

import time
from datetime import datetime

from app.domain.run import Run, RunStatus


def test_submit_creates_queued_run():
    run = Run.submit("summarize the repo")

    assert run.input == "summarize the repo"
    assert run.status is RunStatus.QUEUED
    assert isinstance(run.created_at, datetime)
    assert run.created_at.tzinfo is not None  # timezone-aware


def test_submit_ids_are_uuid7_and_time_ordered():
    earlier = Run.submit("a")
    time.sleep(0.002)  # cross a millisecond boundary; within one ms order is random
    later = Run.submit("b")

    assert earlier.id.version == 7
    assert earlier.id != later.id
    # uuid7 is time-ordered at millisecond granularity (B-tree-friendly inserts)
    assert later.id > earlier.id
