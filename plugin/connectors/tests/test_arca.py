"""Tests for the arca connector (thin HTTP client of NU's afip-ws microservice, Tier A).

arca does not talk to AFIP directly: it calls afip-ws (GET /fiscal/cuit/{cuit}, /health).
These tests mock that microservice with respx and set AFIP_WS_BASE_URL via monkeypatch.

The CUIT used throughout, 20111111112, has a valid modulo-11 checksum.

Live tests would require a reachable afip-ws (over Tailscale) and are marked @live, so
they are excluded from CI and only run when the service is exposed.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mcp_contable.arca import server as arca
from mcp_contable.common import http as http_mod

BASE = "http://afip-ws.test"
VALID_CUIT = "20111111112"  # valid modulo-11 checksum


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture
def _configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set AFIP_WS_BASE_URL so the connector is 'configured'."""
    monkeypatch.setenv(arca.BASE_URL_ENV, BASE)


@pytest.fixture(autouse=True)
def _no_real_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _instant(attempt: int) -> None:
        return None

    monkeypatch.setattr(http_mod, "_sleep_backoff", _instant)


def _assert_envelope(out: dict) -> None:
    assert set(out) >= {
        "data",
        "source_tier",
        "source_url",
        "retrieved_at",
        "notes",
        "citation_flag",
    }
    assert out["source_tier"] == "A"
    assert out["citation_flag"] == ""  # Tier A: no caveat
    assert out["retrieved_at"]


# --------------------------------------------------------------------------- #
# Checksum + validation (no HTTP)                                             #
# --------------------------------------------------------------------------- #


def test_checksum_helper() -> None:
    assert arca._validate_cuit_checksum(VALID_CUIT) is True
    assert arca._validate_cuit_checksum("20111111113") is False  # wrong check digit
    assert arca._validate_cuit_checksum("123") is False


async def test_missing_cuit_returns_error_no_http(_configured: None) -> None:
    with respx.mock:
        route = respx.get(url__startswith=BASE).mock(return_value=httpx.Response(200))
        out = await arca.arca_get_constancia("")
    assert not route.called
    _assert_envelope(out)
    assert out["data"]["error"] == "missing cuit"


async def test_invalid_checksum_returns_error_no_http(_configured: None) -> None:
    with respx.mock:
        route = respx.get(url__startswith=BASE).mock(return_value=httpx.Response(200))
        out = await arca.arca_get_constancia("20-11111111-3")  # bad check digit
    assert not route.called
    _assert_envelope(out)
    assert out["data"]["error"] == "invalid cuit checksum"


# --------------------------------------------------------------------------- #
# Not configured (AFIP_WS_BASE_URL unset)                                     #
# --------------------------------------------------------------------------- #


async def test_not_configured_returns_error_no_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(arca.BASE_URL_ENV, raising=False)
    with respx.mock:
        route = respx.get(url__startswith="http://").mock(
            return_value=httpx.Response(200)
        )
        out = await arca.arca_get_constancia(VALID_CUIT)
    assert not route.called
    _assert_envelope(out)
    assert out["data"]["error"] == "afip-ws not configured"


# --------------------------------------------------------------------------- #
# arca_get_constancia happy path + upstream behaviors                          #
# --------------------------------------------------------------------------- #


async def test_get_constancia_happy_path(_configured: None) -> None:
    payload = {
        "cuit": VALID_CUIT,
        "razon_social": "NU DESARROLLOS SA",
        "domicilio": "Calle Falsa 123",
        "provincia": "Santa Fe",
        "localidad": "Rosario",
        "fiscal_id_type": "CUIT",
        "estado_cuit": "ACTIVO",
        "tipo_persona": "JURIDICA",
        "cached": False,
        "enriched_at": "2026-06-04T12:00:00+00:00",
    }
    with respx.mock:
        respx.get(f"{BASE}/fiscal/cuit/{VALID_CUIT}").mock(
            return_value=httpx.Response(200, json=payload)
        )
        out = await arca.arca_get_constancia(VALID_CUIT)

    _assert_envelope(out)
    data = out["data"]
    assert data["found"] is True
    assert data["razon_social"] == "NU DESARROLLOS SA"
    assert data["estado_cuit"] == "ACTIVO"
    assert data["provincia"] == "Santa Fe"
    assert out["source_url"].endswith(f"/fiscal/cuit/{VALID_CUIT}")


async def test_get_constancia_normalizes_separators(_configured: None) -> None:
    with respx.mock:
        route = respx.get(f"{BASE}/fiscal/cuit/{VALID_CUIT}").mock(
            return_value=httpx.Response(200, json={"cuit": VALID_CUIT, "fiscal_id_type": "CUIT", "cached": False})
        )
        out = await arca.arca_get_constancia("20-11111111-2")
    assert route.called  # separators stripped, checksum valid, request made
    _assert_envelope(out)
    assert out["data"]["found"] is True


async def test_get_constancia_drops_null_fields(_configured: None) -> None:
    payload = {
        "cuit": VALID_CUIT,
        "razon_social": "PERSONA FISICA",
        "domicilio": None,
        "provincia": None,
        "fiscal_id_type": "CUIT",
        "estado_cuit": "ACTIVO",
        "tipo_persona": None,
        "cached": True,
        "enriched_at": None,
    }
    with respx.mock:
        respx.get(f"{BASE}/fiscal/cuit/{VALID_CUIT}").mock(
            return_value=httpx.Response(200, json=payload)
        )
        out = await arca.arca_get_constancia(VALID_CUIT)
    data = out["data"]
    assert "domicilio" not in data  # null dropped
    assert "tipo_persona" not in data
    assert data["razon_social"] == "PERSONA FISICA"


async def test_get_constancia_404_is_not_found(_configured: None) -> None:
    with respx.mock:
        respx.get(f"{BASE}/fiscal/cuit/{VALID_CUIT}").mock(
            return_value=httpx.Response(404, json={"detail": "CUIT no encontrado"})
        )
        out = await arca.arca_get_constancia(VALID_CUIT)
    _assert_envelope(out)
    assert out["data"]["found"] is False
    assert out["data"]["cuit"] == VALID_CUIT
    assert "error" not in out["data"]


async def test_get_constancia_503_is_unavailable(_configured: None) -> None:
    """503 is retryable in common.http; after retries it surfaces as 'unavailable'."""
    with respx.mock:
        respx.get(f"{BASE}/fiscal/cuit/{VALID_CUIT}").mock(
            return_value=httpx.Response(503, json={"detail": "AFIP no disponible"})
        )
        out = await arca.arca_get_constancia(VALID_CUIT)
    _assert_envelope(out)
    assert out["data"]["error"] == "afip-ws unavailable"


async def test_get_constancia_400_carries_status_code(_configured: None) -> None:
    """A non-retryable 4xx surfaces as a graceful error with its status_code."""
    with respx.mock:
        respx.get(f"{BASE}/fiscal/cuit/{VALID_CUIT}").mock(
            return_value=httpx.Response(400, json={"detail": "bad request"})
        )
        out = await arca.arca_get_constancia(VALID_CUIT)
    _assert_envelope(out)
    assert "error" in out["data"]
    assert out["data"]["status_code"] == 400


async def test_get_constancia_source_unavailable(_configured: None) -> None:
    with respx.mock:
        respx.get(f"{BASE}/fiscal/cuit/{VALID_CUIT}").mock(
            side_effect=httpx.ConnectError("refused")
        )
        out = await arca.arca_get_constancia(VALID_CUIT)
    _assert_envelope(out)
    assert out["data"]["error"] == "afip-ws unavailable"


async def test_get_constancia_invalid_json(_configured: None) -> None:
    with respx.mock:
        respx.get(f"{BASE}/fiscal/cuit/{VALID_CUIT}").mock(
            return_value=httpx.Response(200, text="<html>not json</html>")
        )
        out = await arca.arca_get_constancia(VALID_CUIT)
    _assert_envelope(out)
    assert out["data"]["error"] == "invalid JSON from afip-ws"


# --------------------------------------------------------------------------- #
# arca_health                                                                  #
# --------------------------------------------------------------------------- #


async def test_health_happy_path(_configured: None) -> None:
    with respx.mock:
        respx.get(f"{BASE}/health").mock(
            return_value=httpx.Response(
                200, json={"status": "ok", "token_expires_at": "2026-06-04T23:00:00+00:00"}
            )
        )
        out = await arca.arca_health()
    _assert_envelope(out)
    assert out["data"]["status"] == "ok"
    assert out["data"]["token_expires_at"]


async def test_health_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(arca.BASE_URL_ENV, raising=False)
    out = await arca.arca_health()
    _assert_envelope(out)
    assert out["data"]["error"] == "afip-ws not configured"


# --------------------------------------------------------------------------- #
# LIVE -- requires a reachable afip-ws (Tailscale). Excluded from CI.         #
#   Run with AFIP_WS_BASE_URL set: VIRTUAL_ENV= uv run pytest -m live -v      #
# --------------------------------------------------------------------------- #


@pytest.mark.live
async def test_live_health() -> None:
    out = await arca.arca_health()
    assert "error" not in out["data"], out["data"]
    assert out["source_tier"] == "A"
    assert out["data"]["status"]
