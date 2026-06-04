"""Tests for the ckan_nacional connector (datos.jus.gob.ar CKAN Action API, Tier A).

These mock the shared HTTP layer with respx. The connector builds the *full* CKAN
endpoint URL (query string included) and hands it to ``common.fetch`` as the positional
URL -- it does NOT pass ``params=``. So routes are matched here with ``url__startswith``
on ``<BASE>/<action>``, which is robust to query-string ordering/encoding while still
discriminating between actions (package_list vs package_search vs ...).

Live tests (``@pytest.mark.live``) hit the real API and are excluded from CI via
``-m "not live"``.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mcp_contable.ckan_juridico import server as ckan
from mcp_contable.common import http as http_mod

BASE = "https://datos.jus.gob.ar/api/3/action"


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Wipe the connector's process-local TTLCache before & after every test.

    The connector caches package_list and package_show; without this, one test's
    response could satisfy another test's call and mask real behavior.
    """
    ckan._cache.clear()
    yield
    ckan._cache.clear()


@pytest.fixture(autouse=True)
def _no_real_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the HTTP backoff sleep so any retry path is instant (no real delay)."""

    async def _instant(attempt: int) -> None:
        return None

    monkeypatch.setattr(http_mod, "_sleep_backoff", _instant)


def _ckan_ok(result: object) -> dict:
    """Wrap a CKAN ``result`` in the standard success envelope."""
    return {"help": f"{BASE}/help", "success": True, "result": result}


def _ckan_fail(error: object | None = None) -> dict:
    """Build a CKAN logical-failure envelope (success:false), even on HTTP 200."""
    body: dict = {"help": f"{BASE}/help", "success": False}
    if error is not None:
        body["error"] = error
    return body


def _route(action: str) -> str:
    """respx matcher value: match any URL whose path starts with this action."""
    return f"{BASE}/{action}"


def _assert_envelope(out: dict, *, tier: str = "A", citation: str = "") -> None:
    """Common grounding-envelope assertions shared by every tool result."""
    assert set(out) >= {
        "data",
        "source_tier",
        "source_url",
        "retrieved_at",
        "notes",
        "citation_flag",
    }
    assert out["source_tier"] == tier
    assert out["citation_flag"] == citation
    assert out["retrieved_at"]  # populated, non-empty ISO timestamp
    assert out["source_url"].startswith("https://datos.jus.gob.ar/")


# --------------------------------------------------------------------------- #
# ckan_list_datasets                                                          #
# --------------------------------------------------------------------------- #


async def test_list_datasets_happy_path() -> None:
    slugs = [
        "base-de-datos-legislativos-infoleg",
        "base-saij-de-normativa-provincial",
        "centros-de-acceso-a-la-justicia-caj",
    ]
    with respx.mock:
        route = respx.get(url__startswith=_route("package_list")).mock(
            return_value=httpx.Response(200, json=_ckan_ok(slugs))
        )
        out = await ckan.ckan_list_datasets()

    assert route.called
    _assert_envelope(out)  # Tier A => citation_flag == ""
    assert out["data"]["count"] == 3
    assert out["data"]["datasets"] == slugs


async def test_list_datasets_uses_cache_on_second_call() -> None:
    """A second call is served from cache without a second HTTP request."""
    slugs = ["a", "b"]
    with respx.mock:
        route = respx.get(url__startswith=_route("package_list")).mock(
            return_value=httpx.Response(200, json=_ckan_ok(slugs))
        )
        first = await ckan.ckan_list_datasets()
        second = await ckan.ckan_list_datasets()

    assert route.call_count == 1  # cached on the second call
    assert first == second


# --------------------------------------------------------------------------- #
# ckan_search_datasets                                                        #
# --------------------------------------------------------------------------- #


async def test_search_datasets_happy_path_ckan_mode() -> None:
    body = _ckan_ok(
        {
            "count": 2,
            "results": [
                {
                    "name": "base-infoleg",
                    "title": "Base InfoLEG",
                    "notes": "Legislativos.",
                    "resources": [{"id": "r1"}, {"id": "r2"}],
                },
                {
                    "name": "otra-base",
                    "title": "Otra Base",
                    "notes": "",
                    "resources": [],
                },
            ],
        }
    )
    with respx.mock:
        respx.get(url__startswith=_route("package_search")).mock(
            return_value=httpx.Response(200, json=body)
        )
        out = await ckan.ckan_search_datasets("infoleg", rows=10)

    _assert_envelope(out)
    assert out["data"]["count"] == 2
    assert out["data"]["search_mode"] == "ckan"
    first = out["data"]["results"][0]
    assert first["name"] == "base-infoleg"
    assert first["n_resources"] == 2


async def test_search_datasets_client_side_fallback() -> None:
    """count:0 with a non-empty query => paginate q='' and filter client-side.

    First package_search (the real query) returns count:0. The fallback then calls
    package_search again with q='' (rows=1000) and the connector filters titles/slugs/
    notes/tags for the query terms. respx serves both calls via side_effect so we can
    assert it actually fell through and filtered correctly.
    """
    empty = _ckan_ok({"count": 0, "results": []})
    catalog = _ckan_ok(
        {
            "count": 3,
            "results": [
                {
                    "name": "base-de-datos-legislativos-infoleg",
                    "title": "Base de datos legislativos InfoLEG",
                    "notes": "Normas nacionales.",
                    "tags": [{"display_name": "legislacion"}],
                    "resources": [{"id": "r1"}],
                },
                {
                    "name": "centros-acceso-justicia",
                    "title": "Centros de Acceso a la Justicia",
                    "notes": "Ubicaciones.",
                    "tags": [],
                    "resources": [],
                },
                {
                    "name": "another-infoleg-mirror",
                    "title": "Espejo INFOLEG secundario",
                    "notes": "",
                    "tags": [],
                    "resources": [{"id": "x"}, {"id": "y"}],
                },
            ],
        }
    )
    with respx.mock:
        route = respx.get(url__startswith=_route("package_search")).mock(
            side_effect=[
                httpx.Response(200, json=empty),
                httpx.Response(200, json=catalog),
            ]
        )
        out = await ckan.ckan_search_datasets("infoleg")

    assert route.call_count == 2  # query miss, then the q='' wide scan
    _assert_envelope(out)
    assert out["data"]["search_mode"] == "client_side_fallback"
    # Two of three datasets carry "infoleg" in title/slug; the CAJ one does not.
    assert out["data"]["count"] == 2
    names = {r["name"] for r in out["data"]["results"]}
    assert names == {
        "base-de-datos-legislativos-infoleg",
        "another-infoleg-mirror",
    }


async def test_search_datasets_empty_query_stays_ckan_mode() -> None:
    """An empty query never triggers fallback even if count is 0."""
    body = _ckan_ok({"count": 0, "results": []})
    with respx.mock:
        route = respx.get(url__startswith=_route("package_search")).mock(
            return_value=httpx.Response(200, json=body)
        )
        out = await ckan.ckan_search_datasets("   ")

    assert route.call_count == 1  # no fallback scan
    assert out["data"]["search_mode"] == "ckan"
    assert out["data"]["count"] == 0


# --------------------------------------------------------------------------- #
# ckan_get_dataset                                                            #
# --------------------------------------------------------------------------- #


async def test_get_dataset_happy_path_with_resources() -> None:
    pkg = {
        "id": "uuid-1",
        "name": "base-saij-de-normativa-provincial",
        "title": "Base SAIJ de Normativa Provincial",
        "notes": "Normativa provincial.",
        "metadata_created": "2020-01-01T00:00:00",
        "metadata_modified": "2024-01-01T00:00:00",
        "license_title": "CC-BY",
        "author": "Min. Justicia",
        "organization": {"title": "Ministerio de Justicia"},
        "tags": [{"display_name": "normativa"}, {"name": "provincias"}],
        "groups": [{"display_name": "Justicia"}],
        "resources": [
            {
                "id": "res-1",
                "name": "normas.csv",
                "format": "CSV",
                "url": "https://datos.jus.gob.ar/dataset/x/normas.csv",
                "datastore_active": True,
            },
            {
                "id": "res-2",
                "name": "doc.pdf",
                "format": "PDF",
                "url": "https://datos.jus.gob.ar/dataset/x/doc.pdf",
                # datastore_active omitted -> should default to False
            },
        ],
    }
    with respx.mock:
        respx.get(url__startswith=_route("package_show")).mock(
            return_value=httpx.Response(200, json=_ckan_ok(pkg))
        )
        out = await ckan.ckan_get_dataset("base-saij-de-normativa-provincial")

    _assert_envelope(out)
    data = out["data"]
    assert data["name"] == "base-saij-de-normativa-provincial"
    assert data["organization"] == "Ministerio de Justicia"
    assert data["tags"] == ["normativa", "provincias"]
    assert data["n_resources"] == 2
    res = data["resources"]
    assert res[0]["id"] == "res-1"
    assert res[0]["datastore_active"] is True
    assert res[1]["datastore_active"] is False  # defaulted


async def test_get_dataset_empty_slug_returns_error() -> None:
    """An empty slug short-circuits to a grounded error dict (no HTTP call)."""
    with respx.mock:
        route = respx.get(url__startswith=_route("package_show")).mock(
            return_value=httpx.Response(200, json=_ckan_ok({}))
        )
        out = await ckan.ckan_get_dataset("   ")

    assert not route.called
    _assert_envelope(out)
    assert "error" in out["data"]
    assert out["data"]["error"] == "missing dataset slug"


# --------------------------------------------------------------------------- #
# ckan_get_resource_rows                                                      #
# --------------------------------------------------------------------------- #


async def test_get_resource_rows_datastore_success() -> None:
    result = {
        "total": 1500,
        "fields": [
            {"id": "_id", "type": "int"},
            {"id": "norma", "type": "text"},
        ],
        "records": [
            {"_id": 1, "norma": "Ley 27000"},
            {"_id": 2, "norma": "Ley 27001"},
        ],
    }
    with respx.mock:
        respx.get(url__startswith=_route("datastore_search")).mock(
            return_value=httpx.Response(200, json=_ckan_ok(result))
        )
        out = await ckan.ckan_get_resource_rows("res-uuid", limit=20)

    _assert_envelope(out)
    data = out["data"]
    assert data["datastore_available"] is True
    assert data["total"] == 1500
    assert data["fields"] == [
        {"id": "_id", "type": "int"},
        {"id": "norma", "type": "text"},
    ]
    assert len(data["records"]) == 2


async def test_get_resource_rows_http_409_is_download_only() -> None:
    """HTTP 409 => download-only result (datastore_available:false), NOT an error."""
    with respx.mock:
        respx.get(url__startswith=_route("datastore_search")).mock(
            return_value=httpx.Response(409, json={"success": False})
        )
        out = await ckan.ckan_get_resource_rows("res-uuid")

    _assert_envelope(out)
    assert out["data"]["datastore_available"] is False
    assert "error" not in out["data"]
    assert "message" in out["data"]


async def test_get_resource_rows_success_false_http_200_is_download_only() -> None:
    """HTTP 200 + success:false => also a download-only result, not an error."""
    with respx.mock:
        respx.get(url__startswith=_route("datastore_search")).mock(
            return_value=httpx.Response(200, json=_ckan_fail({"message": "not found"}))
        )
        out = await ckan.ckan_get_resource_rows("res-uuid")

    _assert_envelope(out)
    assert out["data"]["datastore_available"] is False
    assert "error" not in out["data"]


async def test_get_resource_rows_empty_id_returns_error() -> None:
    with respx.mock:
        route = respx.get(url__startswith=_route("datastore_search")).mock(
            return_value=httpx.Response(200, json=_ckan_ok({}))
        )
        out = await ckan.ckan_get_resource_rows("")

    assert not route.called
    assert "error" in out["data"]
    assert out["data"]["error"] == "missing resource_id"


async def test_get_resource_rows_http_500_returns_error() -> None:
    """A non-409/404 hard status (e.g. 500) surfaces as a graceful error dict."""
    with respx.mock:
        respx.get(url__startswith=_route("datastore_search")).mock(
            return_value=httpx.Response(500)
        )
        out = await ckan.ckan_get_resource_rows("res-uuid")

    _assert_envelope(out)
    assert "error" in out["data"]


# --------------------------------------------------------------------------- #
# Graceful error handling (never raises to the MCP boundary)                  #
# --------------------------------------------------------------------------- #


async def test_source_unavailable_returns_error_not_raise() -> None:
    """A connection error is turned into a grounded error dict, never raised."""
    with respx.mock:
        respx.get(url__startswith=_route("package_list")).mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        out = await ckan.ckan_list_datasets()

    _assert_envelope(out)
    assert "error" in out["data"]
    assert out["data"]["error"] == "source unavailable"


async def test_ckan_success_false_returns_error() -> None:
    """CKAN success:false (HTTP 200) => graceful error dict for catalog actions."""
    with respx.mock:
        respx.get(url__startswith=_route("package_show")).mock(
            return_value=httpx.Response(200, json=_ckan_fail({"message": "Not found"}))
        )
        out = await ckan.ckan_get_dataset("does-not-exist")

    _assert_envelope(out)
    assert "error" in out["data"]
    assert out["data"]["error"] == "CKAN reported success=false"


async def test_invalid_json_returns_error() -> None:
    """A 200 with a non-JSON body becomes a graceful error, not a crash."""
    with respx.mock:
        respx.get(url__startswith=_route("package_list")).mock(
            return_value=httpx.Response(200, text="<html>not json</html>")
        )
        out = await ckan.ckan_list_datasets()

    _assert_envelope(out)
    assert "error" in out["data"]
    assert out["data"]["error"] == "invalid JSON in CKAN response"


# --------------------------------------------------------------------------- #
# LIVE tests -- hit the real datos.jus.gob.ar API. Excluded from CI.          #
#   Run with:  VIRTUAL_ENV= uv run pytest -m live -v                          #
# --------------------------------------------------------------------------- #


@pytest.mark.live
async def test_live_list_datasets_returns_real_catalog() -> None:
    out = await ckan.ckan_list_datasets()
    assert "error" not in out["data"], out["data"]
    assert out["source_tier"] == "A"
    datasets = out["data"]["datasets"]
    # The real catalog is ~63 datasets; assert a healthy lower bound + a known slug.
    assert out["data"]["count"] >= 40
    assert "base-de-datos-legislativos-infoleg" in datasets


@pytest.mark.live
async def test_live_get_dataset_has_csv_resource() -> None:
    out = await ckan.ckan_get_dataset("base-saij-de-normativa-provincial")
    assert "error" not in out["data"], out["data"]
    assert out["source_tier"] == "A"
    resources = out["data"]["resources"]
    assert resources, "expected at least one resource"
    formats = {(r.get("format") or "").upper() for r in resources}
    assert "CSV" in formats, f"expected a CSV resource, got formats={formats}"
