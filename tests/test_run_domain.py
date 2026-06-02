"""Run domain — submit factory + state machine transitions."""

import time
from datetime import datetime

import pytest

from app.domain.run import InvalidTransition, Run, RunStatus


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


def test_happy_path_state_transitions():
    run = Run.submit("do a thing")
    run.mark_running()
    assert run.status is RunStatus.RUNNING
    run.mark_succeeded()
    assert run.status is RunStatus.SUCCEEDED


def test_happy_path_failure_transition():
    run = Run.submit("do a thing")
    run.mark_running()
    run.mark_failed()
    assert run.status is RunStatus.FAILED


def test_invalid_transition_raises():
    run = Run.submit("do a thing")
    with pytest.raises(InvalidTransition):
        run.mark_succeeded()  # can't skip RUNNING


def test_cancel_from_queued():
    run = Run.submit("do a thing")
    run.mark_cancelled()
    assert run.status is RunStatus.CANCELLED


def test_cancel_from_running():
    run = Run.submit("do a thing")
    run.mark_running()
    run.mark_cancelled()
    assert run.status is RunStatus.CANCELLED


def test_cancel_from_terminal_raises():
    run = Run.submit("do a thing")
    run.mark_running()
    run.mark_succeeded()
    with pytest.raises(InvalidTransition):
        run.mark_cancelled()
