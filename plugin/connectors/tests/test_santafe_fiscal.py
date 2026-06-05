"""Tests for the santafe_fiscal connector (Santa Fe tax-calendar index, Tier B).

The connector scrapes the provincial "Calendarios Impositivos" index page and exposes the
year -> official-URL mapping. It deliberately does NOT fabricate due dates (they are not in
the static HTML). These tests mock the shared HTTP layer with respx using a small HTML
fixture that mirrors the real index structure (anchors with
``/full/<ID>/(subtema)/111353`` hrefs and "Calendario año YYYY" text).

Live tests (``@pytest.mark.live``) hit the real site and are excluded from CI.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mcp_contable.santafe_fiscal import server as sf
from mcp_contable.common import http as http_mod

INDEX_URL = sf.CALENDARIOS_INDEX_URL


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    sf._cache.clear()
    yield
    sf._cache.clear()


@pytest.fixture(autouse=True)
def _no_real_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _instant(attempt: int) -> None:
        return None

    monkeypatch.setattr(http_mod, "_sleep_backoff", _instant)


# A trimmed HTML fixture mirroring the real index: per-year calendars plus a couple of
# entries that MUST be skipped (feriados, "años anteriores").
_INDEX_HTML = """
<html><body>
<div id="contenido">
  <a href="/index.php/web/content/view/full/258328/(subtema)/111353">Calendario año 2026</a>
  <a href="/index.php/web/content/view/full/254195/(subtema)/111353">Calendario año 2025</a>
  <a href="/index.php/web/content/view/full/250502/(subtema)/111353">Calendario año 2024</a>
  <a href="/index.php/web/content/view/full/164906/(subtema)/111353">Calendario de Feriados 2013</a>
  <a href="/index.php/web/content/view/full/190315/(subtema)/111353">Calendarios de años anteriores</a>
  <a href="/index.php/web/content/view/full/102282">Impuestos</a>
</div>
</body></html>
"""


def _html_response(status: int, html: str) -> httpx.Response:
    """Build a response whose body is ISO-8859-1 (as the provincial site serves)."""
    return httpx.Response(
        status,
        content=html.encode("iso-8859-1"),
        headers={"Content-Type": "text/html; charset=ISO-8859-1"},
    )


def _assert_envelope(out: dict) -> None:
    assert set(out) >= {
        "data",
        "source_tier",
        "source_url",
        "retrieved_at",
        "notes",
        "citation_flag",
    }
    assert out["source_tier"] == "B"
    assert out["citation_flag"] == "[scraped -- verificar contra fuente oficial]"
    assert out["retrieved_at"]


# --------------------------------------------------------------------------- #
# santafe_fiscal_list_calendarios                                             #
# --------------------------------------------------------------------------- #


async def test_list_calendarios_happy_path() -> None:
    with respx.mock:
        respx.get(url__startswith=INDEX_URL).mock(
            return_value=_html_response(200, _INDEX_HTML)
        )
        out = await sf.santafe_fiscal_list_calendarios()

    _assert_envelope(out)
    data = out["data"]
    # Only the three per-year calendars; feriados/años-anteriores/impuestos are skipped.
    assert data["count"] == 3
    years = [c["anio"] for c in data["calendarios"]]
    assert years == ["2026", "2025", "2024"]  # most recent first
    first = data["calendarios"][0]
    assert first["url"].startswith("https://www.santafe.gob.ar/")
    assert "258328" in first["url"]


async def test_list_calendarios_uses_cache() -> None:
    with respx.mock:
        route = respx.get(url__startswith=INDEX_URL).mock(
            return_value=_html_response(200, _INDEX_HTML)
        )
        first = await sf.santafe_fiscal_list_calendarios()
        second = await sf.santafe_fiscal_list_calendarios()

    assert route.call_count == 1  # second served from cache
    assert first == second


async def test_list_calendarios_empty_index_is_error() -> None:
    with respx.mock:
        respx.get(url__startswith=INDEX_URL).mock(
            return_value=_html_response(200, "<html><body>nada</body></html>")
        )
        out = await sf.santafe_fiscal_list_calendarios()

    _assert_envelope(out)
    assert out["data"]["error"] == "no calendars found on index page"


async def test_list_calendarios_source_unavailable() -> None:
    with respx.mock:
        respx.get(url__startswith=INDEX_URL).mock(
            side_effect=httpx.ConnectError("refused")
        )
        out = await sf.santafe_fiscal_list_calendarios()

    _assert_envelope(out)
    assert out["data"]["error"] == "source unavailable"


# --------------------------------------------------------------------------- #
# santafe_fiscal_get_calendario                                               #
# --------------------------------------------------------------------------- #


async def test_get_calendario_happy_path() -> None:
    with respx.mock:
        respx.get(url__startswith=INDEX_URL).mock(
            return_value=_html_response(200, _INDEX_HTML)
        )
        out = await sf.santafe_fiscal_get_calendario("2025")

    _assert_envelope(out)
    data = out["data"]
    assert data["anio"] == "2025"
    assert "254195" in data["url"]
    # Honest limitation: dates are not fabricated.
    assert data["detail_available"] is False
    assert "message" in data


async def test_get_calendario_year_not_found() -> None:
    with respx.mock:
        respx.get(url__startswith=INDEX_URL).mock(
            return_value=_html_response(200, _INDEX_HTML)
        )
        out = await sf.santafe_fiscal_get_calendario("1999")

    _assert_envelope(out)
    assert out["data"]["error"] == "calendar not found for that year"
    assert "available_years" in out["data"]


async def test_get_calendario_invalid_year_no_http() -> None:
    with respx.mock:
        route = respx.get(url__startswith=INDEX_URL).mock(
            return_value=_html_response(200, _INDEX_HTML)
        )
        out = await sf.santafe_fiscal_get_calendario("abc")

    assert not route.called  # short-circuits before any HTTP
    _assert_envelope(out)
    assert out["data"]["error"] == "invalid anio"


# --------------------------------------------------------------------------- #
# LIVE -- hits the real Santa Fe site. Excluded from CI.                      #
# --------------------------------------------------------------------------- #


@pytest.mark.live
async def test_live_list_calendarios_has_current_year() -> None:
    out = await sf.santafe_fiscal_list_calendarios()
    assert "error" not in out["data"], out["data"]
    assert out["source_tier"] == "B"
    years = [c["anio"] for c in out["data"]["calendarios"]]
    # The index has historically listed years up to the current one; assert a healthy set.
    assert len(years) >= 5
    assert any(int(y) >= 2024 for y in years)
