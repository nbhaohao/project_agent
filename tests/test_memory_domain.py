"""Memory domain — factory and basic invariants."""

from datetime import datetime

from app.domain.memory import Memory


def test_create_sets_fields():
    m = Memory.create("the sky is blue")

    assert m.content == "the sky is blue"
    assert m.id.version == 7
    assert isinstance(m.created_at, datetime)
    assert m.created_at.tzinfo is not None


def test_create_ids_are_unique():
    a = Memory.create("a")
    b = Memory.create("b")

    assert a.id != b.id
