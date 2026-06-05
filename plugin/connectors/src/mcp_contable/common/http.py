"""Shared async HTTP client for all connectors.

ZERO-RETENTION GUARANTEE
========================
This module is the *only* sanctioned way for a connector to make an HTTP request.
Connectors must never instantiate ``httpx`` directly, because that would bypass the
confidentiality guarantee enforced here:

    * Request bodies are NEVER logged.
    * Response bodies are NEVER logged.
    * Query params and headers (which can carry identifying or sensitive data)
      are NEVER logged.
    * Only non-sensitive *metadata* is ever emitted: the URL host, the HTTP method,
      the status code, the elapsed latency, and the attempt number.

Accounting/tax queries can reveal a client's income, fiscal situation, CUITs, or
documents. Treating every body as confidential and never persisting it is a hard
requirement of this project, not a nice-to-have. Any change to this file must preserve
that guarantee.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional
from urllib.parse import urlsplit

import httpx

# Module logger. NOTE (zero-retention): only ever pass non-sensitive metadata to this
# logger. Never interpolate request/response bodies, params, headers, or full URLs
# (a full URL can leak query params) into a log record.
logger = logging.getLogger("mcp_contable.http")

# Identifiable, polite User-Agent so upstream operators can recognize our traffic.
USER_AGENT = "MCP-Contable/0.1"

# Default per-request timeout (seconds). Override per call.
DEFAULT_TIMEOUT = 20.0

# Retry policy for transient failures only.
MAX_ATTEMPTS = 3
# Status codes considered transient (server-side / gateway). 4xx are NOT retried.
_RETRYABLE_STATUS = frozenset({500, 502, 503, 504})
# Base for exponential backoff: sleep = _BACKOFF_BASE * 2**(attempt-1) seconds.
_BACKOFF_BASE = 0.5


class HttpError(Exception):
    """Base class for all errors raised by this module."""


class SourceUnavailableError(HttpError):
    """The upstream source could not be reached or kept failing transiently.

    Raised after exhausting retries on timeouts / connection errors / retryable 5xx.
    Connectors should catch this and return a graceful, explained error result
    (never let it crash the MCP tool).
    """


class SourceResponseError(HttpError):
    """The upstream responded, but with a non-retryable error status (e.g. 4xx).

    Carries the offending status code so the connector can react (404 vs 403, etc.).
    The response body is intentionally NOT attached, to honor zero-retention.
    """

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def _host(url: str) -> str:
    """Extract just the host from a URL for safe (param-free) logging."""
    try:
        return urlsplit(url).netloc or "?"
    except Exception:  # pragma: no cover - defensive; never block a request on this
        return "?"


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff delay for a given 1-based attempt number."""
    return _BACKOFF_BASE * (2 ** (attempt - 1))


async def fetch(
    url: str,
    *,
    method: str = "GET",
    params: Optional[Mapping[str, Any]] = None,
    data: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> httpx.Response:
    """Perform an HTTP request with retry/backoff and zero body logging.

    Transient failures (timeouts, connection errors, and ``500/502/503/504``) are
    retried up to :data:`MAX_ATTEMPTS` times with exponential backoff. Non-retryable
    error statuses (most ``4xx``) fail fast.

    Parameters
    ----------
    url:
        Absolute request URL.
    method:
        HTTP method (default ``"GET"``).
    params:
        Optional query parameters (sent in the URL query string). Never logged.
    data:
        Optional form fields sent as an ``application/x-www-form-urlencoded`` request
        BODY (httpx ``data=``). Use this when the upstream reads ``$_POST`` / a real
        request body rather than the query string. Like every body, it is NEVER logged.
    headers:
        Optional extra headers, merged over the default ``User-Agent``. Never logged.
    timeout:
        Per-request timeout in seconds (default :data:`DEFAULT_TIMEOUT`).

    Returns
    -------
    httpx.Response
        The successful response (status < 400). The caller owns parsing the body.

    Raises
    ------
    SourceResponseError
        On a non-retryable error status (e.g. 4xx, or a 5xx not in the retry set).
    SourceUnavailableError
        When the source is unreachable or keeps failing transiently after all
        retries.
    """
    merged_headers: dict[str, str] = {"User-Agent": USER_AGENT}
    if headers:
        merged_headers.update(headers)

    host = _host(url)
    last_exc: Optional[Exception] = None

    # A fresh AsyncClient per call keeps the stdio process stateless and avoids
    # leaking connection state between unrelated accounting/tax queries.
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    headers=merged_headers,
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                # Transient network-level failure. Log metadata ONLY (no url/params).
                last_exc = exc
                logger.warning(
                    "http transient failure host=%s method=%s attempt=%d/%d kind=%s",
                    host,
                    method,
                    attempt,
                    MAX_ATTEMPTS,
                    type(exc).__name__,
                )
                if attempt < MAX_ATTEMPTS:
                    await _sleep_backoff(attempt)
                    continue
                raise SourceUnavailableError(
                    f"Source {host!r} unreachable after {MAX_ATTEMPTS} attempts."
                ) from exc

            status = response.status_code

            # Retryable server-side error: back off and try again.
            if status in _RETRYABLE_STATUS and attempt < MAX_ATTEMPTS:
                logger.warning(
                    "http retryable status host=%s method=%s status=%d attempt=%d/%d",
                    host,
                    method,
                    status,
                    attempt,
                    MAX_ATTEMPTS,
                )
                await _sleep_backoff(attempt)
                continue

            # Non-retryable error status (or exhausted retries on a 5xx).
            if status >= 400:
                logger.info(
                    "http error status host=%s method=%s status=%d",
                    host,
                    method,
                    status,
                )
                if status in _RETRYABLE_STATUS:
                    raise SourceUnavailableError(
                        f"Source {host!r} failed with {status} after "
                        f"{MAX_ATTEMPTS} attempts."
                    )
                raise SourceResponseError(
                    f"Source {host!r} returned status {status}.",
                    status_code=status,
                )

            # Success. Log metadata only -- no body, no params.
            logger.debug(
                "http ok host=%s method=%s status=%d attempt=%d",
                host,
                method,
                status,
                attempt,
            )
            return response

    # Unreachable in practice (loop either returns or raises), but keeps types honest.
    raise SourceUnavailableError(
        f"Source {host!r} unreachable."
    ) from last_exc


async def _sleep_backoff(attempt: int) -> None:
    """Sleep for the backoff interval of ``attempt`` (kept separate for testability)."""
    import asyncio

    await asyncio.sleep(_backoff_seconds(attempt))
