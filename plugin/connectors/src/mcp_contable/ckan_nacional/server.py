"""FastMCP server for the CKAN Action API of datos.gob.ar (Tier A).

This is the *reference* connector for MCP-Contable. It wraps the official CKAN Action
API of Argentina's national open-data portal (datos.gob.ar) and exposes a small set of
tools that let Claude discover datasets, inspect their metadata/resources, and read
rows from those resources that live in CKAN's datastore.

Use cases for accounting/tax work: tax-revenue datasets (recaudación tributaria), MiPyME
registry, social-security series, and any other fiscal open data published nationally.

Design rules honored here (see connectors/CLAUDE.md):

    * All HTTP goes through ``common.fetch`` -- never instantiate ``httpx`` directly.
      That preserves the project's zero-retention guarantee.
    * Every tool returns ``to_dict(ground(...))`` with ``SourceTier.A`` -- never raw
      upstream data.
    * Tools NEVER raise to the MCP boundary. Any failure (source unreachable, bad
      status, invalid JSON, or CKAN ``success: false``) is turned into a grounded,
      explained error dict so Claude can reason about it.

ABOUT THE FULL-TEXT SEARCH (``q=``)
===================================
CKAN's Solr full-text index can be uneven for some terms. When a ``q=`` search yields
zero hits this tool performs a *local* fallback: it pages the full dataset list with an
empty query and filters titles/names/notes/tags client-side for the query terms. That
fallback is flagged in the result ``notes``.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import urlencode

from fastmcp import FastMCP

from mcp_contable.common import (
    SourceResponseError,
    SourceTier,
    SourceUnavailableError,
    TTLCache,
    fetch,
    ground,
    to_dict,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Base URL of the CKAN Action API. Every endpoint is ``<BASE>/<action>``.
CKAN_BASE = "https://datos.gob.ar/api/3/action"

#: Tier for this whole connector: an official, structured API => authoritative.
TIER = SourceTier.A

#: Per-request timeout (seconds). Generous: the datastore can be slow for big rows.
HTTP_TIMEOUT = 30.0

#: TTL for cacheable, slow-moving responses (package_list / package_show), in seconds.
_CACHE_TTL = 900.0

#: Process-local cache. Safe per common/cache.py (single event loop, no persistence).
_cache = TTLCache(default_ttl=_CACHE_TTL)

mcp = FastMCP("ckan-nacional")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _endpoint_url(action: str, params: Optional[dict[str, Any]] = None) -> str:
    """Build the full, human-readable CKAN endpoint URL (used as ``source_url``)."""
    url = f"{CKAN_BASE}/{action}"
    if params:
        clean = {k: v for k, v in params.items() if v not in (None, "")}
        if clean:
            url = f"{url}?{urlencode(clean)}"
    return url


def _error(
    message: str,
    source_url: str,
    *,
    detail: str = "",
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a grounded error result (same envelope as a success, never raises)."""
    payload: dict[str, Any] = {"error": message}
    if detail:
        payload["detail"] = detail
    if extra:
        payload.update(extra)
    note = f"CKAN request failed: {message}"
    if detail:
        note = f"{note} ({detail})"
    return to_dict(ground(payload, TIER, source_url, notes=note))


async def _ckan_get(
    action: str, params: Optional[dict[str, Any]] = None
) -> tuple[Optional[Any], Optional[dict[str, Any]]]:
    """Call a CKAN action and return ``(result, error_dict)`` (exactly one non-None)."""
    source_url = _endpoint_url(action, params)
    try:
        response = await fetch(source_url, timeout=HTTP_TIMEOUT)
    except SourceUnavailableError as exc:
        return None, _error("source unavailable", source_url, detail=str(exc))
    except SourceResponseError as exc:
        return None, _error(
            f"upstream returned HTTP {exc.status_code}",
            source_url,
            detail=str(exc),
            extra={"status_code": exc.status_code},
        )

    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return None, _error(
            "invalid JSON in CKAN response",
            source_url,
            detail=type(exc).__name__,
        )

    if not isinstance(body, dict) or not body.get("success", False):
        ckan_error = body.get("error") if isinstance(body, dict) else None
        return None, _error(
            "CKAN reported success=false",
            source_url,
            detail=json.dumps(ckan_error) if ckan_error else "no error detail",
        )

    return body.get("result"), None


def _summarize_dataset(pkg: dict[str, Any]) -> dict[str, Any]:
    """Reduce a full CKAN package to a compact, search-result-friendly summary."""
    notes = (pkg.get("notes") or "").strip()
    truncated = notes if len(notes) <= 280 else notes[:277] + "..."
    resources = pkg.get("resources") or []
    return {
        "name": pkg.get("name"),
        "title": pkg.get("title"),
        "notes": truncated,
        "n_resources": len(resources),
    }


def _matches_terms(pkg: dict[str, Any], terms: list[str]) -> bool:
    """Client-side fallback match: do all query terms appear in the package text?"""
    haystack_parts = [
        pkg.get("title") or "",
        pkg.get("name") or "",
        pkg.get("notes") or "",
    ]
    for tag in pkg.get("tags") or []:
        if isinstance(tag, dict):
            haystack_parts.append(tag.get("display_name") or tag.get("name") or "")
    haystack = " ".join(haystack_parts).lower()
    return all(term in haystack for term in terms)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool
async def ckan_list_datasets() -> dict[str, Any]:
    """List the slugs (identifiers) of every dataset on datos.gob.ar.

    Calls CKAN ``package_list``. Best starting point for discovery: returns the full
    catalog as plain string slugs, e.g. ``"sspm-principales-subgrupos-recaudacion-
    tributaria"``. Pass any slug to ``ckan_get_dataset`` to inspect its resources.

    Returns
    -------
    dict
        Grounded result whose ``data`` is ``{"count": int, "datasets": [slug, ...]}``.
    """
    cache_key = ("package_list",)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result, err = await _ckan_get("package_list")
    if err is not None:
        return err

    slugs = result if isinstance(result, list) else []
    source_url = _endpoint_url("package_list")
    out = to_dict(
        ground(
            {"count": len(slugs), "datasets": slugs},
            TIER,
            source_url,
            notes="Full dataset catalog (CKAN package_list) of datos.gob.ar.",
        )
    )
    _cache.set(cache_key, out)
    return out


@mcp.tool
async def ckan_search_datasets(
    query: str, rows: int = 10, start: int = 0
) -> dict[str, Any]:
    """Search datasets on datos.gob.ar (CKAN ``package_search``).

    When a server-side ``q=`` search returns zero results this tool automatically falls
    back to a CLIENT-SIDE scan: it pages the catalog with an empty query and matches
    your terms against each dataset's title, slug, notes and tags. When that fallback is
    used it is flagged in ``notes`` and the payload's ``search_mode`` is
    ``"client_side_fallback"``.

    Parameters
    ----------
    query:
        Free-text query (e.g. "recaudacion", "monotributo", "mipyme"). May be empty to
        page through all datasets.
    rows:
        Max number of results to return (page size). Clamped to 1..100.
    start:
        Zero-based offset for pagination.

    Returns
    -------
    dict
        Grounded result whose ``data`` is
        ``{"count", "search_mode", "results": [{name, title, notes, n_resources}, ...]}``.
    """
    rows = max(1, min(rows, 100))
    start = max(0, start)
    params = {"q": query, "rows": rows, "start": start}
    source_url = _endpoint_url("package_search", params)

    result, err = await _ckan_get("package_search", params)
    if err is not None:
        return err

    result = result if isinstance(result, dict) else {}
    count = int(result.get("count", 0) or 0)
    raw_results = result.get("results") or []
    summarized = [
        _summarize_dataset(pkg) for pkg in raw_results if isinstance(pkg, dict)
    ]

    if count > 0 or not query.strip():
        return to_dict(
            ground(
                {"count": count, "search_mode": "ckan", "results": summarized},
                TIER,
                source_url,
                notes="CKAN package_search on datos.gob.ar.",
            )
        )

    return await _client_side_search(query, rows, start, source_url)


async def _client_side_search(
    query: str, rows: int, start: int, source_url: str
) -> dict[str, Any]:
    """Page the whole catalog with q='' and filter datasets client-side by ``query``."""
    terms = [t for t in query.lower().split() if t]
    wide_params = {"q": "", "rows": 1000, "start": 0}
    result, err = await _ckan_get("package_search", wide_params)
    if err is not None:
        err["data"]["search_mode"] = "client_side_fallback"
        err["source_url"] = source_url
        return err

    result = result if isinstance(result, dict) else {}
    all_pkgs = [p for p in (result.get("results") or []) if isinstance(p, dict)]
    matched = [p for p in all_pkgs if _matches_terms(p, terms)]
    page = matched[start : start + rows]
    summarized = [_summarize_dataset(pkg) for pkg in page]

    return to_dict(
        ground(
            {
                "count": len(matched),
                "search_mode": "client_side_fallback",
                "results": summarized,
            },
            TIER,
            source_url,
            notes=(
                "CKAN full-text search returned 0 hits for this query. Results below "
                "come from a client-side scan of dataset titles/slugs/notes/tags via "
                "package_search(q='')."
            ),
        )
    )


@mcp.tool
async def ckan_get_dataset(slug: str) -> dict[str, Any]:
    """Fetch a dataset's full metadata and its downloadable resources.

    Calls CKAN ``package_show`` for the given ``slug`` (a dataset ``name``, obtained from
    ``ckan_list_datasets`` or ``ckan_search_datasets``).

    The substantive data usually lives in the resources' downloadable CSV files: use each
    resource's ``url`` to download it, or try ``ckan_get_resource_rows`` with a resource
    ``id`` to read rows directly when that resource is in CKAN's datastore.

    Parameters
    ----------
    slug:
        The dataset ``name`` / slug to look up.

    Returns
    -------
    dict
        Grounded result whose ``data`` carries dataset metadata plus a ``resources``
        list of ``{id, name, format, url, datastore_active}`` entries.
    """
    slug = (slug or "").strip()
    if not slug:
        return _error(
            "missing dataset slug",
            _endpoint_url("package_show"),
            detail="provide a dataset slug, e.g. from ckan_list_datasets",
        )

    cache_key = ("package_show", slug)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    params = {"id": slug}
    source_url = _endpoint_url("package_show", params)
    result, err = await _ckan_get("package_show", params)
    if err is not None:
        return err

    pkg = result if isinstance(result, dict) else {}
    resources = []
    for res in pkg.get("resources") or []:
        if not isinstance(res, dict):
            continue
        resources.append(
            {
                "id": res.get("id"),
                "name": res.get("name"),
                "format": res.get("format"),
                "url": res.get("url"),
                "datastore_active": bool(res.get("datastore_active", False)),
            }
        )

    org = pkg.get("organization") or {}
    data = {
        "id": pkg.get("id"),
        "name": pkg.get("name"),
        "title": pkg.get("title"),
        "notes": pkg.get("notes"),
        "metadata_created": pkg.get("metadata_created"),
        "metadata_modified": pkg.get("metadata_modified"),
        "license_title": pkg.get("license_title"),
        "author": pkg.get("author"),
        "organization": org.get("title") if isinstance(org, dict) else None,
        "tags": [
            t.get("display_name") or t.get("name")
            for t in (pkg.get("tags") or [])
            if isinstance(t, dict)
        ],
        "groups": [
            g.get("display_name") or g.get("name")
            for g in (pkg.get("groups") or [])
            if isinstance(g, dict)
        ],
        "n_resources": len(resources),
        "resources": resources,
    }

    out = to_dict(
        ground(
            data,
            TIER,
            source_url,
            notes="CKAN package_show. Substantive data lives in the resource CSV urls.",
        )
    )
    _cache.set(cache_key, out)
    return out


@mcp.tool
async def ckan_get_resource_rows(
    resource_id: str, limit: int = 20, query: str = ""
) -> dict[str, Any]:
    """Read rows from a dataset resource via CKAN's datastore (``datastore_search``).

    Many resources are NOT loaded into the queryable datastore -- they are published only
    as downloadable CSV files. For those, CKAN returns an error (typically HTTP 409 /
    ``success: false``); this tool handles that gracefully and tells you the resource is
    download-only (use ``ckan_get_dataset`` to obtain its CSV ``url``).

    Parameters
    ----------
    resource_id:
        The resource ``id`` (a UUID, obtained from ``ckan_get_dataset``).
    limit:
        Max rows to return. Clamped to 1..100.
    query:
        Optional free-text filter passed to the datastore (``q=``).

    Returns
    -------
    dict
        Grounded result. On success ``data`` is
        ``{"total", "fields", "records"}``; for a download-only resource ``data``
        explains that and includes ``datastore_available: false``.
    """
    resource_id = (resource_id or "").strip()
    if not resource_id:
        return _error(
            "missing resource_id",
            _endpoint_url("datastore_search"),
            detail="provide a resource id, e.g. from ckan_get_dataset",
        )

    limit = max(1, min(limit, 100))
    params: dict[str, Any] = {"resource_id": resource_id, "limit": limit}
    if query:
        params["q"] = query
    source_url = _endpoint_url("datastore_search", params)

    try:
        response = await fetch(source_url, timeout=HTTP_TIMEOUT)
    except SourceResponseError as exc:
        if exc.status_code in (404, 409):
            return to_dict(
                ground(
                    {
                        "datastore_available": False,
                        "resource_id": resource_id,
                        "message": (
                            "This resource is not loaded into CKAN's datastore, so its "
                            "rows cannot be queried directly. It is published as a "
                            "downloadable file. Use ckan_get_dataset to obtain the "
                            "resource's CSV 'url' and download it instead."
                        ),
                    },
                    TIER,
                    source_url,
                    notes=(
                        f"datastore_search returned HTTP {exc.status_code}: resource "
                        "is download-only (not in datastore)."
                    ),
                )
            )
        return _error(
            f"upstream returned HTTP {exc.status_code}",
            source_url,
            detail=str(exc),
            extra={"status_code": exc.status_code},
        )
    except SourceUnavailableError as exc:
        return _error("source unavailable", source_url, detail=str(exc))

    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return _error(
            "invalid JSON in CKAN response",
            source_url,
            detail=type(exc).__name__,
        )

    if not isinstance(body, dict) or not body.get("success", False):
        return to_dict(
            ground(
                {
                    "datastore_available": False,
                    "resource_id": resource_id,
                    "message": (
                        "This resource is not queryable via the datastore (CKAN reported "
                        "success=false). It is likely download-only; use ckan_get_dataset "
                        "to obtain its CSV 'url'."
                    ),
                },
                TIER,
                source_url,
                notes="datastore_search success=false: resource is download-only.",
            )
        )

    result = body.get("result") or {}
    fields = result.get("fields") or []
    records = result.get("records") or []
    data = {
        "datastore_available": True,
        "resource_id": resource_id,
        "total": result.get("total"),
        "fields": [
            {"id": f.get("id"), "type": f.get("type")}
            for f in fields
            if isinstance(f, dict)
        ],
        "records": records,
    }
    return to_dict(
        ground(data, TIER, source_url, notes="CKAN datastore_search rows.")
    )


if __name__ == "__main__":
    # Run as a stdio MCP server. Do NOT invoke this in a non-interactive smoke test --
    # it would block waiting for stdio.
    mcp.run()
