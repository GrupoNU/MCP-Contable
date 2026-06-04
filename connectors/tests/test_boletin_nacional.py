"""Tests for the boletin_nacional connector (Boletin Oficial scraper, Tier B).

These mock the shared HTTP layer with respx. The connector builds the full
``detalleAviso`` URL and hands it to ``common.fetch`` as the positional URL (no
``params=``), so routes are matched with ``url__startswith`` on the BORA base path.

The HTML fixtures below are modeled on the REAL page structure verified against the
live site (2026-06): an aviso's title lives in ``#tituloDetalleAviso`` and its full
body in ``#cuerpoDetalleAviso``, both present in the initial HTML (NOT JS-rendered). A
non-existent aviso returns HTTP 200 with a shell page lacking both elements.

Live tests (``@pytest.mark.live``) hit the real site and are excluded from CI via
``-m "not live"``.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mcp_contable.boletin_nacional import server as bora
from mcp_contable.common import http as http_mod

BASE = "https://www.boletinoficial.gob.ar"


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Wipe the connector's process-local TTLCache before & after every test."""
    bora._cache.clear()
    yield
    bora._cache.clear()


@pytest.fixture(autouse=True)
def _no_real_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the HTTP backoff sleep so any retry path is instant (no real delay)."""

    async def _instant(attempt: int) -> None:
        return None

    monkeypatch.setattr(http_mod, "_sleep_backoff", _instant)


def _aviso_html(
    *,
    titulo: str = "LEY DE MODERNIZACION LABORAL",
    subtitulo: str = "Ley 27802",
    cuerpo: str = "El Senado y Camara de Diputados sancionan. ARTICULO 1: Disposiciones.",
    fecha_pub: str = "06/03/2026",
    page_title: str = "BOLETIN OFICIAL - LEY DE MODERNIZACION LABORAL - Ley 27802",
) -> str:
    """Build HTML shaped like a real detalleAviso page (title + body present)."""
    return f"""<!DOCTYPE html>
<html>
<head><title>{page_title}</title></head>
<body>
  <div class="row" id="detalleAviso">
    <div id="tituloDetalleAviso" class="col-md-12 form-group">
      <h1>{titulo}</h1>
      <h2>{subtitulo}</h2>
    </div>
    <div id="cuerpoDetalleAviso" class="col-md-12">
      <style>table tr td {{border: 1px solid grey;}}</style>
      <p>{cuerpo}</p>
      <p><small>Fecha de publicacion {fecha_pub}</small></p>
    </div>
  </div>
</body>
</html>"""


def _notfound_html() -> str:
    """Shell page the site returns (HTTP 200) for a non-existent aviso: no content ids."""
    return """<!DOCTYPE html>
<html>
<head><title>BOLETIN OFICIAL REPUBLICA ARGENTINA</title></head>
<body>
  <div id="layoutContent">
    <div id="btnVolver">Volver</div>
  </div>
</body>
</html>"""


def _js_only_html() -> str:
    """Page with the title element but an EMPTY body (simulates JS-rendered body)."""
    return """<!DOCTYPE html>
<html>
<head><title>BOLETIN OFICIAL - algo</title></head>
<body>
  <div id="detalleAviso">
    <div id="tituloDetalleAviso"><h1>UN TITULO</h1></div>
    <div id="cuerpoDetalleAviso"></div>
  </div>
</body>
</html>"""


def _route(seccion: str = "primera") -> str:
    """respx matcher: match any URL whose path starts with the detalleAviso section."""
    return f"{BASE}/detalleAviso/{seccion}"


def _assert_envelope(out: dict) -> None:
    """Common grounding-envelope assertions: Tier B carries the scraped citation flag."""
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
    assert out["retrieved_at"]  # populated, non-empty ISO timestamp
    assert out["source_url"].startswith("https://www.boletinoficial.gob.ar/")


# --------------------------------------------------------------------------- #
# boletin_get_aviso -- happy path                                             #
# --------------------------------------------------------------------------- #


async def test_get_aviso_happy_path_extracts_title_and_body() -> None:
    with respx.mock:
        route = respx.get(url__startswith=_route("primera")).mock(
            return_value=httpx.Response(200, html=_aviso_html())
        )
        out = await bora.boletin_get_aviso("339128", "20260306", "primera")

    assert route.called
    _assert_envelope(out)
    data = out["data"]
    assert data["found"] is True
    assert data["aviso_id"] == "339128"
    assert data["seccion"] == "primera"
    assert data["fecha"] == "20260306"
    assert "MODERNIZACION LABORAL" in data["titulo"]
    assert "Ley 27802" in data["titulo"]
    # Body text extracted, with the inline <style> stripped out.
    assert "ARTICULO 1" in data["texto"]
    assert "border: 1px solid grey" not in data["texto"]
    assert data["texto_chars"] > 0
    assert data["fecha_publicacion"] == "06/03/2026"


async def test_get_aviso_source_url_is_canonical() -> None:
    with respx.mock:
        respx.get(url__startswith=_route("primera")).mock(
            return_value=httpx.Response(200, html=_aviso_html())
        )
        out = await bora.boletin_get_aviso("339128", "20260306", "primera")

    assert (
        out["source_url"]
        == "https://www.boletinoficial.gob.ar/detalleAviso/primera/339128/20260306"
    )


async def test_get_aviso_uses_cache_on_second_call() -> None:
    """A second call for the same aviso is served from cache (no second HTTP request)."""
    with respx.mock:
        route = respx.get(url__startswith=_route("primera")).mock(
            return_value=httpx.Response(200, html=_aviso_html())
        )
        first = await bora.boletin_get_aviso("339128", "20260306", "primera")
        second = await bora.boletin_get_aviso("339128", "20260306", "primera")

    assert route.call_count == 1  # cached on the second call
    assert first == second


# --------------------------------------------------------------------------- #
# boletin_get_aviso -- not found / JS-only (honest, never fabricated)         #
# --------------------------------------------------------------------------- #


async def test_get_aviso_not_found_reports_found_false() -> None:
    """HTTP 200 shell page with no content ids => found:false, not an error/crash."""
    with respx.mock:
        respx.get(url__startswith=_route("primera")).mock(
            return_value=httpx.Response(200, html=_notfound_html())
        )
        out = await bora.boletin_get_aviso("99999999", "20260306", "primera")

    _assert_envelope(out)
    data = out["data"]
    assert data["found"] is False
    assert "error" not in data
    assert "message" in data


async def test_get_aviso_not_found_is_not_cached() -> None:
    """A not-found result must not be cached (the id may become valid later)."""
    with respx.mock:
        route = respx.get(url__startswith=_route("primera")).mock(
            return_value=httpx.Response(200, html=_notfound_html())
        )
        await bora.boletin_get_aviso("99999999", "20260306", "primera")
        await bora.boletin_get_aviso("99999999", "20260306", "primera")

    assert route.call_count == 2  # not served from cache


async def test_get_aviso_empty_body_reports_js_limitation() -> None:
    """Title present but body empty => honest 'possible JS-rendered body' message."""
    with respx.mock:
        respx.get(url__startswith=_route("primera")).mock(
            return_value=httpx.Response(200, html=_js_only_html())
        )
        out = await bora.boletin_get_aviso("339128", "20260306", "primera")

    _assert_envelope(out)
    data = out["data"]
    assert data["found"] is True
    assert data["texto"] == ""
    assert data["texto_chars"] == 0
    assert "message" in data
    assert "JavaScript" in data["message"] or "JavaScript" in out["notes"]


# --------------------------------------------------------------------------- #
# boletin_get_aviso -- input validation (no HTTP call)                        #
# --------------------------------------------------------------------------- #


async def test_get_aviso_missing_id_returns_error() -> None:
    with respx.mock:
        route = respx.get(url__startswith=_route("primera")).mock(
            return_value=httpx.Response(200, html=_aviso_html())
        )
        out = await bora.boletin_get_aviso("   ", "20260306", "primera")

    assert not route.called
    _assert_envelope(out)
    assert out["data"]["error"] == "missing aviso_id"


async def test_get_aviso_invalid_seccion_returns_error() -> None:
    with respx.mock:
        route = respx.get(url__startswith=f"{BASE}/detalleAviso").mock(
            return_value=httpx.Response(200, html=_aviso_html())
        )
        out = await bora.boletin_get_aviso("339128", "20260306", "cuarta")

    assert not route.called
    assert out["data"]["error"] == "invalid seccion"


async def test_get_aviso_invalid_fecha_returns_error() -> None:
    with respx.mock:
        route = respx.get(url__startswith=f"{BASE}/detalleAviso").mock(
            return_value=httpx.Response(200, html=_aviso_html())
        )
        out = await bora.boletin_get_aviso("339128", "2026-03-06", "primera")

    assert not route.called
    assert out["data"]["error"] == "invalid fecha"


# --------------------------------------------------------------------------- #
# boletin_get_aviso -- graceful transport errors (never raises)               #
# --------------------------------------------------------------------------- #


async def test_get_aviso_source_unavailable_returns_error() -> None:
    """A connection error becomes a grounded error dict, never raised."""
    with respx.mock:
        respx.get(url__startswith=_route("primera")).mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        out = await bora.boletin_get_aviso("339128", "20260306", "primera")

    _assert_envelope(out)
    assert out["data"]["error"] == "source unavailable"


async def test_get_aviso_http_404_returns_error() -> None:
    """A hard 4xx surfaces as a graceful error dict with the status code."""
    with respx.mock:
        respx.get(url__startswith=_route("primera")).mock(
            return_value=httpx.Response(404, html="<html>not found</html>")
        )
        out = await bora.boletin_get_aviso("339128", "20260306", "primera")

    _assert_envelope(out)
    assert "error" in out["data"]
    assert out["data"]["status_code"] == 404


async def test_get_aviso_http_500_returns_error() -> None:
    """A 5xx (after retries) surfaces as 'source unavailable', not a crash."""
    with respx.mock:
        respx.get(url__startswith=_route("primera")).mock(
            return_value=httpx.Response(500)
        )
        out = await bora.boletin_get_aviso("339128", "20260306", "primera")

    _assert_envelope(out)
    assert "error" in out["data"]


# --------------------------------------------------------------------------- #
# boletin_list_seccion -- honest "not viable" stub                            #
# --------------------------------------------------------------------------- #


async def test_list_seccion_reports_not_viable() -> None:
    """Listing is JS-rendered: tool returns found:false with an explanation, no HTTP."""
    with respx.mock:
        route = respx.get(url__startswith=f"{BASE}/seccion").mock(
            return_value=httpx.Response(200, html="<html></html>")
        )
        out = await bora.boletin_list_seccion("primera", "20260306")

    assert not route.called  # the stub does not actually fetch
    _assert_envelope(out)
    data = out["data"]
    assert data["found"] is False
    assert data["avisos"] == []
    assert "JavaScript" in data["message"]


async def test_list_seccion_invalid_seccion_returns_error() -> None:
    out = await bora.boletin_list_seccion("cuarta", "20260306")
    assert out["data"]["error"] == "invalid seccion"


async def test_list_seccion_invalid_fecha_returns_error() -> None:
    out = await bora.boletin_list_seccion("primera", "bad")
    assert out["data"]["error"] == "invalid fecha"


# --------------------------------------------------------------------------- #
# LIVE tests -- hit the real boletinoficial.gob.ar. Excluded from CI.         #
#   Run with:  VIRTUAL_ENV= uv run pytest -m live -v                          #
# --------------------------------------------------------------------------- #


@pytest.mark.live
async def test_live_get_real_aviso_extracts_body() -> None:
    """The real aviso /detalleAviso/primera/339128/20260306 must yield real body text.

    This is the load-bearing live check: it proves the aviso content is in the static
    HTML (not JS-only) and that the parser extracts it.
    """
    out = await bora.boletin_get_aviso("339128", "20260306", "primera")
    assert "error" not in out["data"], out["data"]
    assert out["source_tier"] == "B"
    assert out["citation_flag"] == "[scraped -- verificar contra fuente oficial]"
    data = out["data"]
    assert data["found"] is True, data
    assert data["titulo"], "expected a non-empty title"
    # Body must be substantial real legal prose (the real aviso is ~200 KB of text).
    assert data["texto_chars"] > 1000, data["texto_chars"]
    assert "ARTICULO" in data["texto"].upper() or "ARTÍCULO" in data["texto"].upper()


@pytest.mark.live
async def test_live_nonexistent_aviso_reports_found_false() -> None:
    """A clearly non-existent id should be reported as found:false (not fabricated)."""
    out = await bora.boletin_get_aviso("99999999", "20260306", "primera")
    assert "error" not in out["data"], out["data"]
    assert out["data"]["found"] is False
