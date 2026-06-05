"""Shared building blocks used by every connector.

Connectors should import everything they need from here, e.g.::

    from mcp_contable.common import fetch, ground, SourceTier, to_dict
"""

from __future__ import annotations

from .cache import TTLCache, cached_call
from .grounding import (
    GroundedResult,
    SourceTier,
    ground,
    to_dict,
    verify_marker,
)
from .http import (
    DEFAULT_TIMEOUT,
    USER_AGENT,
    HttpError,
    SourceResponseError,
    SourceUnavailableError,
    fetch,
)

__all__ = [
    # http
    "fetch",
    "HttpError",
    "SourceUnavailableError",
    "SourceResponseError",
    "USER_AGENT",
    "DEFAULT_TIMEOUT",
    # grounding
    "ground",
    "to_dict",
    "verify_marker",
    "GroundedResult",
    "SourceTier",
    # cache
    "TTLCache",
    "cached_call",
]
