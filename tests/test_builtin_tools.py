"""Unit tests for built-in tools — no real network/LLM."""

import pytest

from app.application.agent.tools.builtin import (
    FILE_READ,
    GET_CURRENT_TIME,
    HTTP_FETCH,
    _FETCH_MAX_CHARS,
    _file_read,
    _get_current_time,
    _http_fetch,
    build_registry,
)


# ── get_current_time ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_time_returns_iso8601():
    result = await _get_current_time({})
    # basic ISO-8601 sanity: contains 'T' and '+' or 'Z'
    assert "T" in result
    assert "+" in result or result.endswith("Z")


# ── http_fetch ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_http_fetch_truncates_large_response(monkeypatch):
    big_text = "x" * (_FETCH_MAX_CHARS + 1000)

    class _FakeResponse:
        text = big_text

        def raise_for_status(self) -> None:
            pass

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def get(self, *args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr("app.application.agent.tools.builtin.httpx.AsyncClient", _FakeClient)
    result = await _http_fetch({"url": "http://example.com"})
    assert len(result) == _FETCH_MAX_CHARS


# ── file_read ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_read_happy_path(tmp_path, monkeypatch):
    (tmp_path / "hello.txt").write_text("hello world")
    monkeypatch.setattr("app.application.agent.tools.builtin.settings.tool_fs_root", str(tmp_path))
    result = await _file_read({"path": "hello.txt"})
    assert result == "hello world"


@pytest.mark.asyncio
async def test_file_read_blocks_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("app.application.agent.tools.builtin.settings.tool_fs_root", str(tmp_path))
    with pytest.raises(PermissionError, match="path traversal denied"):
        await _file_read({"path": "../etc/passwd"})


# ── build_registry ────────────────────────────────────────────────────────────


def test_build_registry_no_allowed_hides_network_and_fs():
    reg = build_registry(allowed=set())
    names = {s["name"] for s in reg.schemas()}
    assert "get_current_time" in names
    assert "http_fetch" not in names
    assert "file_read" not in names


def test_build_registry_with_network_exposes_http_fetch():
    reg = build_registry(allowed={"network"})
    names = {s["name"] for s in reg.schemas()}
    assert "http_fetch" in names
    assert "file_read" not in names


def test_build_registry_with_all_exposes_all_tools():
    reg = build_registry(allowed={"network", "fs_read"})
    names = {s["name"] for s in reg.schemas()}
    assert names == {"get_current_time", "http_fetch", "file_read"}
