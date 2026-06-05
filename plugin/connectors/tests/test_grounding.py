"""Tests for the source-tier grounding system (anti-hallucination guarantee)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from mcp_contable.common import (
    GroundedResult,
    SourceTier,
    ground,
    to_dict,
    verify_marker,
)


def test_source_tier_serializes_to_letter() -> None:
    """SourceTier inherits from str, so .value is the bare letter."""
    assert SourceTier.A.value == "A"
    assert SourceTier.B.value == "B"
    assert SourceTier.C.value == "C"
    # str-inheritance means it compares equal to the plain string too.
    assert SourceTier.A == "A"


def test_ground_populates_fields() -> None:
    """ground() carries data / tier / url / notes through unchanged."""
    payload = {"norma": "Ley 27.000"}
    result = ground(
        payload,
        SourceTier.A,
        "https://datos.jus.gob.ar/dataset/x",
        notes="inferred field",
    )
    assert isinstance(result, GroundedResult)
    assert result.data is payload
    assert result.source_tier is SourceTier.A
    assert result.source_url == "https://datos.jus.gob.ar/dataset/x"
    assert result.notes == "inferred field"


def test_ground_notes_default_empty() -> None:
    """notes defaults to an empty string when omitted."""
    result = ground("data", SourceTier.B, "https://example.test")
    assert result.notes == ""


def test_ground_auto_populates_retrieved_at_iso8601_utc() -> None:
    """retrieved_at is auto-stamped and is a parseable ISO-8601 UTC timestamp."""
    before = datetime.now(timezone.utc)
    result = ground("data", SourceTier.A, "https://example.test")
    after = datetime.now(timezone.utc)

    assert result.retrieved_at, "retrieved_at must be auto-populated"
    parsed = datetime.fromisoformat(result.retrieved_at)
    # Must carry timezone info and be UTC.
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(None)
    # And it must fall within the window the call happened in.
    assert before <= parsed <= after


@pytest.mark.parametrize(
    ("tier", "expected"),
    [
        (SourceTier.A, ""),
        (SourceTier.B, "[scraped -- verificar contra fuente oficial]"),
        (SourceTier.C, "[verify]"),
    ],
)
def test_verify_marker_per_tier(tier: SourceTier, expected: str) -> None:
    """verify_marker returns the right caveat for each tier."""
    assert verify_marker(tier) == expected


def test_to_dict_full_shape() -> None:
    """to_dict returns the complete public contract dict."""
    result = ground(
        {"k": "v"},
        SourceTier.A,
        "https://example.test/x",
        notes="n",
    )
    d = to_dict(result)
    assert set(d.keys()) == {
        "data",
        "source_tier",
        "source_url",
        "retrieved_at",
        "notes",
        "citation_flag",
    }
    assert d["data"] == {"k": "v"}
    # source_tier is serialized to the bare string value, not the Enum.
    assert d["source_tier"] == "A"
    assert isinstance(d["source_tier"], str)
    assert d["source_url"] == "https://example.test/x"
    assert d["retrieved_at"] == result.retrieved_at
    assert d["notes"] == "n"


@pytest.mark.parametrize(
    ("tier", "expected_flag"),
    [
        (SourceTier.A, ""),
        (SourceTier.B, "[scraped -- verificar contra fuente oficial]"),
        (SourceTier.C, "[verify]"),
    ],
)
def test_to_dict_citation_flag_per_tier(tier: SourceTier, expected_flag: str) -> None:
    """citation_flag in the dict matches verify_marker(tier)."""
    result = ground("data", tier, "https://example.test")
    assert to_dict(result)["citation_flag"] == expected_flag


def test_grounded_result_is_frozen() -> None:
    """GroundedResult is immutable: assigning to a field raises."""
    result = ground("data", SourceTier.A, "https://example.test")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.data = "mutated"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.source_tier = SourceTier.C  # type: ignore[misc]
