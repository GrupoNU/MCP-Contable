"""Tests for the shared async HTTP client (retry, errors, zero-retention logging)."""

from __future__ import annotations

import logging

import httpx
import pytest
import respx

from mcp_contable.common import (
    DEFAULT_TIMEOUT,
    USER_AGENT,
    SourceResponseError,
    SourceUnavailableError,
    fetch,
)
from mcp_contable.common import http as http_mod

BASE = "https://datos.example.test"
URL = f"{BASE}/api/3/action/package_show"


@pytest.fixture(autouse=True)
def _no_real_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the backoff sleep so retry tests are instant (no real delay)."""

    async def _instant(attempt: int) -> None:
        return None

    monkeypatch.setattr(http_mod, "_sleep_backoff", _instant)


async def test_happy_path_returns_response() -> None:
    """A 200 yields the httpx.Response unchanged."""
    with respx.mock:
        route = respx.get(URL).mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        resp = await fetch(URL)
        assert isinstance(resp, httpx.Response)
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert route.called


async def test_404_raises_source_response_error_with_status() -> None:
    """A 4xx fails fast as SourceResponseError carrying the status code."""
    with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(404))
        with pytest.raises(SourceResponseError) as exc_info:
            await fetch(URL)
        assert exc_info.value.status_code == 404


async def test_4xx_does_not_retry() -> None:
    """A non-retryable 4xx is requested exactly once."""
    with respx.mock:
        route = respx.get(URL).mock(return_value=httpx.Response(403))
        with pytest.raises(SourceResponseError):
            await fetch(URL)
        assert route.call_count == 1


async def test_503_retried_then_success() -> None:
    """A transient 503 is retried and a subsequent 200 succeeds."""
    with respx.mock:
        route = respx.get(URL).mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        resp = await fetch(URL)
        assert resp.status_code == 200
        # Confirm it actually retried (two requests issued).
        assert route.call_count == 2


async def test_persistent_5xx_raises_source_unavailable() -> None:
    """A 5xx that never recovers exhausts retries -> SourceUnavailableError."""
    with respx.mock:
        route = respx.get(URL).mock(return_value=httpx.Response(503))
        with pytest.raises(SourceUnavailableError):
            await fetch(URL)
        assert route.call_count == http_mod.MAX_ATTEMPTS


async def test_persistent_timeout_raises_source_unavailable() -> None:
    """A persistent timeout exhausts retries -> SourceUnavailableError."""
    with respx.mock:
        route = respx.get(URL).mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        with pytest.raises(SourceUnavailableError):
            await fetch(URL)
        assert route.call_count == http_mod.MAX_ATTEMPTS


async def test_timeout_then_success_is_retried() -> None:
    """A single timeout followed by a 200 succeeds after retry."""
    with respx.mock:
        route = respx.get(URL).mock(
            side_effect=[
                httpx.TimeoutException("timed out"),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        resp = await fetch(URL)
        assert resp.status_code == 200
        assert route.call_count == 2


async def test_user_agent_header_sent() -> None:
    """The polite, identifiable User-Agent is attached to the request."""
    with respx.mock:
        route = respx.get(URL).mock(return_value=httpx.Response(200))
        await fetch(URL)
        sent_request = route.calls.last.request
        assert sent_request.headers["User-Agent"] == USER_AGENT
        assert USER_AGENT == "MCP-Contable/0.1"


async def test_default_timeout_constant() -> None:
    """Sanity check on the public default timeout constant."""
    assert DEFAULT_TIMEOUT == 20.0


async def test_params_passed_to_httpx() -> None:
    """Query params provided by the caller reach the wire."""
    with respx.mock:
        route = respx.get(URL).mock(return_value=httpx.Response(200))
        await fetch(URL, params={"id": "ley-27000", "page": "2"})
        sent_url = route.calls.last.request.url
        assert sent_url.params.get("id") == "ley-27000"
        assert sent_url.params.get("page") == "2"


async def test_extra_headers_merged_over_default() -> None:
    """Caller-provided headers are merged with the default User-Agent."""
    with respx.mock:
        route = respx.get(URL).mock(return_value=httpx.Response(200))
        await fetch(URL, headers={"Accept": "application/json"})
        sent = route.calls.last.request
        assert sent.headers["Accept"] == "application/json"
        assert sent.headers["User-Agent"] == USER_AGENT


# --------------------------------------------------------------------------- #
# ZERO-RETENTION: the logger must never see full URLs, paths, or query params. #
# --------------------------------------------------------------------------- #


async def test_logs_never_leak_path_or_params(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Confidentiality guarantee: only the host is logged, never path/params.

    A legal query's path and params can reveal the client's parties or strategy,
    so the logger must surface the host for diagnostics but nothing sensitive.
    """
    sensitive_path = "/secret-case/expediente-12345"
    sensitive_param_value = "cliente-confidencial"
    url = f"{BASE}{sensitive_path}"
    host = "datos.example.test"

    with caplog.at_level(logging.DEBUG, logger="mcp_contable.http"):
        with respx.mock:
            respx.get(url).mock(return_value=httpx.Response(200))
            await fetch(url, params={"parte": sensitive_param_value})

    all_log_text = "\n".join(rec.getMessage() for rec in caplog.records)

    # The host is allowed (non-sensitive metadata for diagnostics).
    assert host in all_log_text
    # The sensitive path and param value must NOT appear anywhere in the logs.
    assert sensitive_path not in all_log_text
    assert "expediente-12345" not in all_log_text
    assert sensitive_param_value not in all_log_text


async def test_transient_failure_logs_no_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Even on retry warnings, the full URL / params never reach the logs."""
    sensitive_path = "/secret-case/expediente-99999"
    url = f"{BASE}{sensitive_path}"

    with caplog.at_level(logging.DEBUG, logger="mcp_contable.http"):
        with respx.mock:
            respx.get(url).mock(side_effect=httpx.TimeoutException("boom"))
            with pytest.raises(SourceUnavailableError):
                await fetch(url, params={"parte": "secreta"})

    all_log_text = "\n".join(rec.getMessage() for rec in caplog.records)
    # There must be warning records (the retries logged something).
    assert any(rec.levelno == logging.WARNING for rec in caplog.records)
    assert sensitive_path not in all_log_text
    assert "expediente-99999" not in all_log_text
    assert "secreta" not in all_log_text
