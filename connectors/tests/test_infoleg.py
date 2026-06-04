"""Tests for the infoleg connector (servicios.infoleg.gob.ar, Tier B HTML scraper).

These mock the shared HTTP layer with respx. The connector builds the full verNorma.do
URL (``?id=<n>``) and hands it to ``common.fetch`` as the positional URL, so routes are
matched here with ``url__startswith`` on the verNorma.do base.

The success cassette (``NORMA_HTML``) is the REAL server-rendered block of
``verNorma.do?id=423722`` (Ley 27801), captured live during development and trimmed to
the parsed region. It is served as latin-1 bytes so the connector's ISO-8859-1 decoding
path is exercised (accented chars in the resumen).

Live tests (``@pytest.mark.live``) hit the real site and are excluded from CI via
``-m "not live"``.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mcp_contable.common import http as http_mod
from mcp_contable.infoleg import server as infoleg

VER_NORMA = "https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do"


# --------------------------------------------------------------------------- #
# Cassettes                                                                    #
# --------------------------------------------------------------------------- #

#: Real InfoLEG verNorma.do?id=423722 (Ley 27801) markup -- the parsed region verbatim.
#: Note the ISO-8859-1 entities/accents (AÑOS) so encoding handling is covered.
NORMA_HTML = """<html><head><meta charset="ISO-8859-1"><title>InfoLeg</title></head>
<body>
<div id="resultados_caja"><div id="resultados">
<div id="Textos_Completos">
    <p>
        <strong>
            Ley&nbsp; 27801 &nbsp; HONORABLE CONGRESO DE LA NACION ARGENTINA <br/>
        </strong>
        <span class="vr_azul11"> 27-feb-2026 </span>
    </p>
    <span class="destacado"> REGIMEN PENAL JUVENIL </span>
    <br/>
    <h1> DISPOSICIONES </h1>
    <p>
        Publicada en el Bolet&iacute;n Oficial del
        <a href="//www.infoleg.gob.ar/?page_id=216&amp;id=35866">09-mar-2026</a>
        &nbsp;&nbsp; N&uacute;mero:
        <a href="//www.infoleg.gob.ar/?page_id=216&amp;id=35866">35866</a>
        &nbsp;&nbsp; P&aacute;gina: 4
    </p>
    <br/>
    <p>
        <strong> Resumen:</strong><br/>
        EL OBJETO DE LA PRESENTE LEY ES EL ESTABLECIMIENTO DEL REGIMEN PENAL APLICABLE
        A LAS PERSONAS ADOLESCENTES, DESDE LOS CATORCE (14) AÑOS DE EDAD.
    </p>
    <br/>
    <p>
        <a href='anexos/420000-424999/423722/norma.htm'><b>Texto completo de la norma</b></a>
    </p>
</div>
</div></div>
</body></html>"""

#: An InfoLEG error/empty page that lacks the #Textos_Completos block.
EMPTY_HTML = (
    "<html><head><title>InfoLeg</title></head><body>"
    "<div id='wrap'><p>No se encontr&oacute; la norma.</p></div>"
    "</body></html>"
)


def _latin1_response(status: int, html: str) -> httpx.Response:
    """Build a response whose body is ISO-8859-1 bytes (as InfoLEG actually serves)."""
    return httpx.Response(
        status,
        content=html.encode("iso-8859-1"),
        headers={"Content-Type": "text/html; charset=ISO-8859-1"},
    )


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Wipe the connector's process-local TTLCache before & after every test."""
    infoleg._cache.clear()
    yield
    infoleg._cache.clear()


@pytest.fixture(autouse=True)
def _no_real_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the HTTP backoff sleep so any retry path is instant (no real delay)."""

    async def _instant(attempt: int) -> None:
        return None

    monkeypatch.setattr(http_mod, "_sleep_backoff", _instant)


def _assert_envelope(out: dict) -> None:
    """Common grounding-envelope assertions for every infoleg tool result (Tier B)."""
    assert set(out) >= {
        "data",
        "source_tier",
        "source_url",
        "retrieved_at",
        "notes",
        "citation_flag",
    }
    assert out["source_tier"] == "B"
    # Tier B always carries the scraped-verification marker.
    assert out["citation_flag"] == "[scraped -- verificar contra fuente oficial]"
    assert out["retrieved_at"]
    assert out["source_url"].startswith("https://servicios.infoleg.gob.ar/")


# --------------------------------------------------------------------------- #
# infoleg_get_norma -- happy path                                             #
# --------------------------------------------------------------------------- #


async def test_get_norma_happy_path_parses_all_fields() -> None:
    with respx.mock:
        route = respx.get(url__startswith=VER_NORMA).mock(
            return_value=_latin1_response(200, NORMA_HTML)
        )
        out = await infoleg.infoleg_get_norma("423722")

    assert route.called
    _assert_envelope(out)
    data = out["data"]
    assert "error" not in data
    assert data["tipo"] == "Ley"
    assert data["numero"] == "27801"
    assert data["organismo"] == "HONORABLE CONGRESO DE LA NACION ARGENTINA"
    assert data["fecha_sancion"] == "27-feb-2026"
    assert data["materia"] == "REGIMEN PENAL JUVENIL"
    assert data["disposicion"] == "DISPOSICIONES"
    assert data["boletin_oficial"] == {
        "fecha": "09-mar-2026",
        "numero": "35866",
        "pagina": "4",
    }
    assert data["resumen"].startswith("EL OBJETO DE LA PRESENTE LEY")
    # ISO-8859-1 was decoded correctly: the Ñ in "AÑOS" survives round-trip.
    assert "AÑOS" in data["resumen"]
    assert data["texto_completo_url"] == (
        "https://servicios.infoleg.gob.ar/infolegInternet/"
        "anexos/420000-424999/423722/norma.htm"
    )


async def test_get_norma_uses_cache_on_second_call() -> None:
    """A second call for the same id is served from cache (no second HTTP request)."""
    with respx.mock:
        route = respx.get(url__startswith=VER_NORMA).mock(
            return_value=_latin1_response(200, NORMA_HTML)
        )
        first = await infoleg.infoleg_get_norma("423722")
        second = await infoleg.infoleg_get_norma("423722")

    assert route.call_count == 1
    assert first == second


# --------------------------------------------------------------------------- #
# infoleg_get_norma -- graceful failures (never raise)                        #
# --------------------------------------------------------------------------- #


async def test_get_norma_empty_html_returns_graceful_error() -> None:
    """A page without the #Textos_Completos block => 'no norma found', not a crash."""
    with respx.mock:
        respx.get(url__startswith=VER_NORMA).mock(
            return_value=_latin1_response(200, EMPTY_HTML)
        )
        out = await infoleg.infoleg_get_norma("999999999")

    _assert_envelope(out)
    assert out["data"]["error"] == "no norma found at this id"


async def test_get_norma_missing_id_returns_error_no_http() -> None:
    with respx.mock:
        route = respx.get(url__startswith=VER_NORMA).mock(
            return_value=_latin1_response(200, NORMA_HTML)
        )
        out = await infoleg.infoleg_get_norma("   ")

    assert not route.called
    _assert_envelope(out)
    assert out["data"]["error"] == "missing norma_id"


async def test_get_norma_non_numeric_id_returns_error_no_http() -> None:
    with respx.mock:
        route = respx.get(url__startswith=VER_NORMA).mock(
            return_value=_latin1_response(200, NORMA_HTML)
        )
        out = await infoleg.infoleg_get_norma("abc")

    assert not route.called
    assert out["data"]["error"] == "invalid norma_id"


async def test_get_norma_source_unavailable_returns_error() -> None:
    """A connection error becomes a grounded error dict, never raised."""
    with respx.mock:
        respx.get(url__startswith=VER_NORMA).mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        out = await infoleg.infoleg_get_norma("423722")

    _assert_envelope(out)
    assert out["data"]["error"] == "source unavailable"


async def test_get_norma_http_404_returns_error() -> None:
    """A non-retryable 4xx surfaces as a graceful error dict with the status code."""
    with respx.mock:
        respx.get(url__startswith=VER_NORMA).mock(
            return_value=httpx.Response(404)
        )
        out = await infoleg.infoleg_get_norma("423722")

    _assert_envelope(out)
    assert "error" in out["data"]
    assert out["data"]["status_code"] == 404


async def test_get_norma_http_503_exhausts_retries_to_error() -> None:
    """Repeated 503 (InfoLEG's typical flakiness) ends as 'source unavailable'."""
    with respx.mock:
        respx.get(url__startswith=VER_NORMA).mock(
            return_value=httpx.Response(503)
        )
        out = await infoleg.infoleg_get_norma("423722")

    _assert_envelope(out)
    assert out["data"]["error"] == "source unavailable"


# --------------------------------------------------------------------------- #
# infoleg_search_norma -- honest "no programmatic search" guidance            #
# --------------------------------------------------------------------------- #


async def test_search_norma_returns_guidance_no_http() -> None:
    """Search makes NO HTTP call and returns honest guidance, never fake results."""
    with respx.mock:
        route = respx.get(url__startswith=VER_NORMA).mock(
            return_value=_latin1_response(200, NORMA_HTML)
        )
        out = await infoleg.infoleg_search_norma(tipo="Ley", numero="27801")

    assert not route.called  # no scraping of the fragile search backend
    _assert_envelope(out)
    data = out["data"]
    assert data["search_available"] is False
    assert data["query"]["tipo"] == "Ley"
    assert data["query"]["numero"] == "27801"
    assert "infoleg_get_norma" in data["guidance"]
    assert data["search_url"].startswith("https://servicios.infoleg.gob.ar/")


# --------------------------------------------------------------------------- #
# LIVE tests -- hit the real InfoLEG site. Excluded from CI.                   #
#   Run with:  VIRTUAL_ENV= uv run pytest tests/test_infoleg.py -m live -v     #
# --------------------------------------------------------------------------- #


@pytest.mark.live
async def test_live_get_norma_extracts_something_reasonable() -> None:
    """Hit the real verNorma.do?id=423722 (Ley 27801) and verify real extraction.

    InfoLEG's backend is flaky; the shared HTTP layer retries transient 5xx. If the
    source is genuinely down at test time this asserts a graceful error envelope rather
    than a crash, but normally it should parse the Ley 27801 fields.
    """
    out = await infoleg.infoleg_get_norma("423722")
    assert out["source_tier"] == "B"
    assert out["citation_flag"] == "[scraped -- verificar contra fuente oficial]"

    data = out["data"]
    if "error" in data:
        pytest.skip(f"InfoLEG unavailable at test time: {data}")

    # Something legislatively meaningful must come back: either the law number/type or
    # the subject/summary mentioning the regimen penal juvenil of Ley 27801.
    blob = " ".join(str(v) for v in data.values()).lower()
    assert data.get("numero") == "27801" or "penal" in blob or "ley" in blob
    assert data.get("source_url", out["source_url"]).startswith(
        "https://servicios.infoleg.gob.ar/"
    )
