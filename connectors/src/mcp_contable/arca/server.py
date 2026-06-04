"""FastMCP server for ARCA (ex-AFIP) Constancia de Inscripcion / Padron (Tier A).

This connector does NOT talk to AFIP directly and does NOT handle the AFIP certificate.
Instead it is a thin HTTP client of NU's **afip-ws** microservice (FastAPI), which already
runs on NU's VPS, holds NU's AFIP certificate (the same one Odoo uses) and is authorized
for the ``ws_sr_constancia_inscripcion`` web service. afip-ws exposes:

    GET /fiscal/cuit/{cuit}   -> razon_social, estado, domicilio, actividad, tipo_persona
    GET /health               -> service status + WSAA token expiry

Because afip-ws wraps an official, structured AFIP web service, results are grounded as
:data:`SourceTier.A` (authoritative; no scraping caveat). The certificate lives ONLY on
the VPS; MCP-Contable never sees it.

CONFIGURATION
=============
The afip-ws base URL is read from the ``AFIP_WS_BASE_URL`` environment variable (e.g.
``http://100.88.25.41:8001`` over the GrupoNU Tailscale network). If it is unset, the
tools return a grounded, explained error telling the operator to configure it -- they
never guess an endpoint and never fabricate fiscal data.

Design rules honored here (see connectors/CLAUDE.md):

    * All HTTP goes through ``common.fetch`` -- never instantiate ``httpx`` directly.
    * Every tool returns ``to_dict(ground(...))`` -- never raw upstream data.
    * Tools NEVER raise to the MCP boundary; failures become grounded, explained results.
    * Zero-retention: CUITs and fiscal data are never logged (common/http guarantees it).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from fastmcp import FastMCP

from mcp_contable.common import (
    SourceResponseError,
    SourceTier,
    SourceUnavailableError,
    fetch,
    ground,
    to_dict,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Env var holding the afip-ws base URL (e.g. "http://100.88.25.41:8001").
BASE_URL_ENV = "AFIP_WS_BASE_URL"

#: Tier for this connector: afip-ws wraps an official AFIP web service => authoritative.
TIER = SourceTier.A

#: Per-request timeout (seconds). The first call may trigger a WSAA token fetch upstream.
HTTP_TIMEOUT = 30.0

#: CUIT/CUIL checksum weights (modulo 11), same as afip-ws.
_CUIT_WEIGHTS = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]

mcp = FastMCP("arca")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _base_url() -> Optional[str]:
    """Return the configured afip-ws base URL (no trailing slash), or None if unset."""
    raw = (os.getenv(BASE_URL_ENV) or "").strip()
    return raw.rstrip("/") or None


def _validate_cuit_checksum(cuit_digits: str) -> bool:
    """Validate a CUIT/CUIL checksum (modulo 11). Input: exactly 11 digits."""
    if len(cuit_digits) != 11 or not cuit_digits.isdigit():
        return False
    total = sum(int(d) * w for d, w in zip(cuit_digits[:10], _CUIT_WEIGHTS))
    check = 11 - (total % 11)
    if check == 11:
        check = 0
    elif check == 10:
        check = 9
    return int(cuit_digits[10]) == check


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
    note = f"ARCA (afip-ws) request failed: {message}"
    if detail:
        note = f"{note} ({detail})"
    return to_dict(ground(payload, TIER, source_url, notes=note))


def _not_configured_error(action: str) -> dict[str, Any]:
    """Grounded error for the 'AFIP_WS_BASE_URL not set' case (no HTTP attempted)."""
    return _error(
        "afip-ws not configured",
        f"<{BASE_URL_ENV} unset>",
        detail=(
            f"set {BASE_URL_ENV} to the afip-ws base URL (e.g. http://100.88.25.41:8001 "
            f"over Tailscale) to use {action}. The connector never guesses the endpoint."
        ),
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool
async def arca_get_constancia(cuit: str) -> dict[str, Any]:
    """Fetch a taxpayer's AFIP Constancia de Inscripcion by CUIT (Tier A).

    Calls NU's afip-ws (``GET /fiscal/cuit/{cuit}``), which queries AFIP's
    ``ws_sr_constancia_inscripcion`` web service with NU's certificate. Returns the
    authoritative fiscal identity of the CUIT.

    The ``cuit`` may be passed with or without separators (``20-12345678-9`` or
    ``20123456789``); it is normalized to 11 digits and its checksum (modulo 11) is
    validated locally before any request -- an invalid CUIT short-circuits with an error
    and no HTTP call.

    Returns
    -------
    dict
        Grounded result (``source_tier="A"``). On success ``data`` includes (fields are
        present only when AFIP returns them):

            * ``cuit``           -- the normalized 11-digit CUIT
            * ``razon_social``   -- legal name / apellido+nombre
            * ``estado_cuit``    -- clave status (e.g. "ACTIVO")
            * ``tipo_persona``   -- "FISICA" / "JURIDICA"
            * ``domicilio``      -- fiscal address
            * ``provincia`` / ``localidad``
            * ``actividad_principal`` (when provided by afip-ws)
            * ``cached``         -- whether afip-ws served it from its own cache
            * ``enriched_at``    -- afip-ws enrichment timestamp

        On a not-found CUIT, ``data`` is ``{"found": false, "cuit": ...}``. On a
        configuration or upstream failure, ``data`` is ``{"error": ...}``.
    """
    digits = re.sub(r"\D", "", cuit or "")
    if not digits:
        return _error(
            "missing cuit",
            f"<{BASE_URL_ENV}>/fiscal/cuit/",
            detail="provide a CUIT, e.g. 20-12345678-9 or 20123456789",
        )
    if not _validate_cuit_checksum(digits):
        return _error(
            "invalid cuit checksum",
            f"<{BASE_URL_ENV}>/fiscal/cuit/{digits}",
            detail="the CUIT failed the modulo-11 checksum; check the digits",
        )

    base = _base_url()
    if base is None:
        return _not_configured_error("arca_get_constancia")

    source_url = f"{base}/fiscal/cuit/{digits}"

    try:
        response = await fetch(source_url, timeout=HTTP_TIMEOUT)
    except SourceUnavailableError as exc:
        return _error("afip-ws unavailable", source_url, detail=str(exc))
    except SourceResponseError as exc:
        # afip-ws returns 404 when the CUIT is unknown to AFIP, 422 for a bad checksum
        # (we already guard that), 503 when AFIP itself is down.
        if exc.status_code == 404:
            return to_dict(
                ground(
                    {"found": False, "cuit": digits},
                    TIER,
                    source_url,
                    notes="afip-ws: CUIT not found in AFIP.",
                )
            )
        return _error(
            f"afip-ws returned HTTP {exc.status_code}",
            source_url,
            detail=str(exc),
            extra={"status_code": exc.status_code},
        )

    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return _error(
            "invalid JSON from afip-ws",
            source_url,
            detail=type(exc).__name__,
        )

    if not isinstance(body, dict):
        return _error("unexpected afip-ws payload", source_url)

    # Map afip-ws FiscalResponse -> our grounded data (drop nulls for a clean payload).
    data: dict[str, Any] = {"found": True}
    for key in (
        "cuit",
        "razon_social",
        "estado_cuit",
        "tipo_persona",
        "domicilio",
        "provincia",
        "localidad",
        "actividad_principal",
        "fiscal_id_type",
        "cached",
        "enriched_at",
    ):
        if key in body and body[key] is not None:
            data[key] = body[key]

    return to_dict(
        ground(
            data,
            TIER,
            source_url,
            notes=(
                "AFIP Constancia de Inscripcion via NU's afip-ws "
                "(ws_sr_constancia_inscripcion). Authoritative (Tier A)."
            ),
        )
    )


@mcp.tool
async def arca_health() -> dict[str, Any]:
    """Check whether NU's afip-ws is reachable and its WSAA token status.

    Calls ``GET /health`` on afip-ws. Useful to confirm connectivity (e.g. over Tailscale)
    before relying on ``arca_get_constancia``.

    Returns
    -------
    dict
        Grounded result whose ``data`` is ``{"status": ..., "token_expires_at": ...}`` on
        success, or ``{"error": ...}`` when afip-ws is unconfigured/unreachable.
    """
    base = _base_url()
    if base is None:
        return _not_configured_error("arca_health")

    source_url = f"{base}/health"
    try:
        response = await fetch(source_url, timeout=HTTP_TIMEOUT)
    except SourceUnavailableError as exc:
        return _error("afip-ws unavailable", source_url, detail=str(exc))
    except SourceResponseError as exc:
        return _error(
            f"afip-ws returned HTTP {exc.status_code}",
            source_url,
            detail=str(exc),
            extra={"status_code": exc.status_code},
        )

    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return _error("invalid JSON from afip-ws", source_url, detail=type(exc).__name__)

    data = {
        "status": body.get("status") if isinstance(body, dict) else None,
        "token_expires_at": body.get("token_expires_at")
        if isinstance(body, dict)
        else None,
    }
    return to_dict(
        ground(data, TIER, source_url, notes="afip-ws /health.")
    )


if __name__ == "__main__":
    # Run as a stdio MCP server. Do NOT invoke this in a non-interactive smoke test --
    # it would block waiting for stdio.
    mcp.run()
