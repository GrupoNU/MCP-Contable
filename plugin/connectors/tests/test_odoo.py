"""Tests for the odoo connector (XML-RPC client of NU's Odoo 18, Tier A).

The connector talks to Odoo via ``xmlrpc.client.ServerProxy``. These tests replace that
proxy with a fake so no real Odoo is contacted. Config is injected via monkeypatch env.

Safety is the point of several tests: writes default to DRAFT; posting only happens on
explicit opt-in (auto_post), authorized for the 3-year migration (2026-06-06).

Live tests (``@pytest.mark.live``) need a reachable Odoo + valid API key and are excluded
from CI; run with the ODOO_* env set.
"""

from __future__ import annotations

import xmlrpc.client

import pytest

from mcp_contable.odoo import server as odoo

URL = "https://odoo.test"
DB = "gruponu_production"


# --------------------------------------------------------------------------- #
# Fake XML-RPC proxy                                                          #
# --------------------------------------------------------------------------- #


class _FakeCommon:
    """Stands in for the /common endpoint."""

    def __init__(self, version=None, uid=7, auth_raises=None):
        self._version = version or {"server_version": "18.0-test"}
        self._uid = uid
        self._auth_raises = auth_raises

    def version(self):
        return self._version

    def authenticate(self, db, user, key, ctx):
        if self._auth_raises:
            raise self._auth_raises
        return self._uid


class _FakeObject:
    """Stands in for the /object endpoint. ``handler`` maps (model, method) -> result."""

    def __init__(self, handler):
        self._handler = handler
        self.calls = []  # records (model, method, args, kwargs)

    def execute_kw(self, db, uid, key, model, method, args, kwargs):
        self.calls.append((model, method, args, kwargs))
        return self._handler(model, method, args, kwargs)


def _install_fake(monkeypatch, *, common=None, handler=None, obj_holder=None):
    """Patch odoo._proxy to return fakes. Returns the FakeObject for assertions."""
    common = common or _FakeCommon()
    fake_obj = _FakeObject(handler or (lambda *a: []))
    if obj_holder is not None:
        obj_holder["obj"] = fake_obj

    def _fake_proxy(endpoint):
        return common if endpoint == "common" else fake_obj

    monkeypatch.setattr(odoo, "_proxy", _fake_proxy)
    return fake_obj


@pytest.fixture
def _configured(monkeypatch):
    monkeypatch.setenv(odoo.URL_ENV, URL)
    monkeypatch.setenv(odoo.DB_ENV, DB)
    monkeypatch.setenv(odoo.USER_ENV, "mcp-contable@gruponu.com")
    monkeypatch.setenv(odoo.API_KEY_ENV, "secret-key")
    monkeypatch.delenv(odoo.COMPANY_ENV, raising=False)


def _assert_envelope(out: dict, *, citation: str = "") -> None:
    assert set(out) >= {"data", "source_tier", "source_url", "retrieved_at", "notes", "citation_flag"}
    assert out["source_tier"] == "A"
    assert out["citation_flag"] == citation
    assert out["retrieved_at"]
    # The API key must never leak into the grounded source_url.
    assert "secret-key" not in out["source_url"]


# --------------------------------------------------------------------------- #
# Config / not configured                                                     #
# --------------------------------------------------------------------------- #


async def test_health_not_configured(monkeypatch):
    for e in (odoo.URL_ENV, odoo.DB_ENV, odoo.USER_ENV, odoo.API_KEY_ENV):
        monkeypatch.delenv(e, raising=False)
    out = await odoo.odoo_health()
    _assert_envelope(out)
    assert out["data"]["error"] == "odoo not configured"


async def test_read_tool_not_configured(monkeypatch):
    monkeypatch.delenv(odoo.URL_ENV, raising=False)
    out = await odoo.odoo_get_plan_cuentas()
    assert out["data"]["error"] == "odoo not configured"


# --------------------------------------------------------------------------- #
# health                                                                       #
# --------------------------------------------------------------------------- #


async def test_health_happy_path(_configured, monkeypatch):
    _install_fake(monkeypatch, common=_FakeCommon(version={"server_version": "18.0-20251222"}, uid=7))
    out = await odoo.odoo_health()
    _assert_envelope(out)
    assert out["data"]["reachable"] is True
    assert out["data"]["authenticated"] is True
    assert out["data"]["server_version"] == "18.0-20251222"
    assert out["data"]["uid"] == 7


async def test_health_auth_fails(_configured, monkeypatch):
    _install_fake(monkeypatch, common=_FakeCommon(uid=False))
    out = await odoo.odoo_health()
    _assert_envelope(out)
    assert out["data"]["reachable"] is True
    assert out["data"]["authenticated"] is False


async def test_health_unreachable(_configured, monkeypatch):
    def _boom(endpoint):
        raise OSError("connection refused")

    monkeypatch.setattr(odoo, "_proxy", _boom)
    out = await odoo.odoo_health()
    _assert_envelope(out)
    assert out["data"]["error"] == "odoo unreachable"


# --------------------------------------------------------------------------- #
# read tools                                                                   #
# --------------------------------------------------------------------------- #


async def test_get_company(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("res.company", "search"):
            return [1, 2]
        if (model, method) == ("res.company", "read"):
            return [
                {"id": 1, "name": "NU Desarrollos Conscientes S.R.L.", "vat": "30717928993", "currency_id": [3, "ARS"]},
                {"id": 2, "name": "Vastu inmobiliaria", "vat": False, "currency_id": [3, "ARS"]},
            ]
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_get_company()
    _assert_envelope(out)
    assert out["data"]["count"] == 2
    names = {c["name"] for c in out["data"]["companies"]}
    assert "NU Desarrollos Conscientes S.R.L." in names
    assert out["data"]["companies"][0]["currency"] == "ARS"


async def test_get_plan_cuentas(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.account", "search"):
            return [10, 11]
        if (model, method) == ("account.account", "read"):
            return [
                {"id": 10, "code": "111000", "name": "Caja", "account_type": "asset_cash", "reconcile": False},
                {"id": 11, "code": "411000", "name": "Ventas", "account_type": "income", "reconcile": False},
            ]
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_get_plan_cuentas()
    _assert_envelope(out)
    assert out["data"]["count"] == 2
    assert out["data"]["accounts"][0]["code"] == "111000"


async def test_get_plan_cuentas_scopes_with_company_ids_odoo18(_configured, monkeypatch):
    """Odoo 18: account.account is multi-company -> filter by company_ids, NOT company_id.

    Regression guard: filtering account.account by company_id raises
    'Invalid field account.account.company_id' in Odoo 18.
    """
    monkeypatch.setenv(odoo.COMPANY_ENV, "1")
    captured = {}

    def handler(model, method, args, kwargs):
        if (model, method) == ("account.account", "search"):
            captured["domain"] = args[0]
            return [10]
        if (model, method) == ("account.account", "read"):
            return [{"id": 10, "code": "1", "name": "x", "account_type": "income", "reconcile": False}]
        return []

    _install_fake(monkeypatch, handler=handler)
    await odoo.odoo_get_plan_cuentas()
    # The domain must use company_ids (m2m 'in'), never company_id.
    flat = str(captured["domain"])
    assert "company_ids" in flat, captured["domain"]
    assert "('company_id'," not in flat, captured["domain"]


async def test_buscar_partner_by_cuit(_configured, monkeypatch):
    holder = {}
    def handler(model, method, args, kwargs):
        if (model, method) == ("res.partner", "search"):
            # assert the domain filtered by vat (11-digit cuit path)
            return [5]
        if (model, method) == ("res.partner", "read"):
            return [{"id": 5, "name": "Proveedor SA", "vat": "30111111118", "is_company": True}]
        return []

    _install_fake(monkeypatch, handler=handler, obj_holder=holder)
    out = await odoo.odoo_buscar_partner("30-11111111-8")
    _assert_envelope(out)
    assert out["data"]["count"] == 1
    assert out["data"]["partners"][0]["vat"] == "30111111118"


async def test_get_comprobantes_empty(_configured, monkeypatch):
    _install_fake(monkeypatch, handler=lambda *a: [])
    out = await odoo.odoo_get_comprobantes(estado="posted")
    _assert_envelope(out)
    assert out["data"]["count"] == 0
    assert out["data"]["moves"] == []


async def test_check_l10n_ar(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("ir.module.module", "search"):
            return [1, 2, 3]
        if (model, method) == ("ir.module.module", "read"):
            return [{"name": "l10n_ar"}, {"name": "l10n_ar_afipws"}, {"name": "l10n_ar_afipws_fe"}]
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_check_l10n_ar()
    _assert_envelope(out)
    assert out["data"]["l10n_ar"] is True
    assert "l10n_ar_afipws_fe" in out["data"]["installed"]


# --------------------------------------------------------------------------- #
# error handling: Odoo Fault becomes a graceful error                         #
# --------------------------------------------------------------------------- #


async def test_odoo_fault_is_graceful(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        raise xmlrpc.client.Fault(2, "odoo.exceptions.AccessError\nNo tiene permiso")

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_get_diarios()
    _assert_envelope(out)
    assert "error" in out["data"]
    assert "rejected" in out["data"]["error"]


# --------------------------------------------------------------------------- #
# WRITE tools — must create in DRAFT and NEVER post                           #
# --------------------------------------------------------------------------- #


async def test_crear_factura_default_is_draft_no_post(_configured, monkeypatch):
    """Default behaviour (auto_post omitted) stays draft-only — does NOT post."""
    holder = {}

    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move", "create"):
            vals = args[0]
            assert vals.get("state") in (None, "draft")
            assert vals["move_type"] == "in_invoice"
            return 99
        return []

    _install_fake(monkeypatch, handler=handler, obj_holder=holder)
    out = await odoo.odoo_crear_factura_borrador(
        move_type="in_invoice",
        partner_id=5,
        journal_id=2,
        invoice_date="2026-06-05",
        lineas=[{"name": "Servicio", "account_id": 11, "quantity": 1, "price_unit": 1000.0, "tax_ids": [3]}],
    )
    _assert_envelope(out)
    assert out["data"]["id"] == 99
    assert out["data"]["state"] == "draft"
    # Default must NOT post.
    methods = [(m, meth) for (m, meth, _a, _k) in holder["obj"].calls]
    assert ("account.move", "action_post") not in methods


async def test_crear_factura_auto_post_calls_action_post(_configured, monkeypatch):
    """auto_post=True creates then posts; result state is 'posted'."""
    holder = {}

    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move", "create"):
            return 101
        if (model, method) == ("account.move", "action_post"):
            assert args[0] == [101]  # posts the just-created move
            return True
        return []

    _install_fake(monkeypatch, handler=handler, obj_holder=holder)
    out = await odoo.odoo_crear_factura_borrador(
        move_type="out_invoice",
        partner_id=5,
        journal_id=2,
        invoice_date="2026-06-05",
        lineas=[{"name": "Venta", "account_id": 11, "quantity": 1, "price_unit": 1000.0}],
        auto_post=True,
    )
    _assert_envelope(out)
    assert out["data"]["id"] == 101
    assert out["data"]["state"] == "posted"
    methods = [(m, meth) for (m, meth, _a, _k) in holder["obj"].calls]
    assert ("account.move", "action_post") in methods


async def test_crear_factura_auto_post_failure_surfaces_draft_id(_configured, monkeypatch):
    """If posting fails, the move stays draft and the error reports the draft id."""

    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move", "create"):
            return 102
        if (model, method) == ("account.move", "action_post"):
            raise xmlrpc.client.Fault(1, "ValidationError: unbalanced")
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_crear_factura_borrador(
        move_type="out_invoice",
        partner_id=5,
        journal_id=2,
        invoice_date="2026-06-05",
        lineas=[{"name": "Venta", "account_id": 11, "quantity": 1, "price_unit": 1000.0}],
        auto_post=True,
    )
    _assert_envelope(out)
    assert "error" in out["data"]
    assert "id=102" in out["data"]["detail"]


# --------------------------------------------------------------------------- #
# odoo_crear_asiento (manual journal entry, posts by default)                  #
# --------------------------------------------------------------------------- #


async def test_crear_asiento_balanced_posts_by_default(_configured, monkeypatch):
    holder = {}

    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move", "create"):
            vals = args[0]
            assert vals["move_type"] == "entry"
            assert len(vals["line_ids"]) == 2
            return 200
        if (model, method) == ("account.move", "action_post"):
            assert args[0] == [200]
            return True
        return []

    _install_fake(monkeypatch, handler=handler, obj_holder=holder)
    out = await odoo.odoo_crear_asiento(
        fecha="2023-12-31",
        lineas=[
            {"account_id": 11, "debit": 1000.0, "name": "Apertura caja"},
            {"account_id": 22, "credit": 1000.0, "name": "Capital"},
        ],
    )
    _assert_envelope(out)
    assert out["data"]["state"] == "posted"
    assert out["data"]["balanced"] is True
    assert out["data"]["debit_total"] == 1000.0
    methods = [(m, meth) for (m, meth, _a, _k) in holder["obj"].calls]
    assert ("account.move", "action_post") in methods


async def test_crear_asiento_unbalanced_rejected_before_odoo(_configured, monkeypatch):
    """A non-balanced entry is rejected without ever calling create/post."""
    fake = _install_fake(monkeypatch, handler=lambda *a: 1)
    out = await odoo.odoo_crear_asiento(
        fecha="2023-12-31",
        lineas=[
            {"account_id": 11, "debit": 1000.0},
            {"account_id": 22, "credit": 900.0},
        ],
    )
    _assert_envelope(out)
    assert out["data"]["error"] == "entry not balanced"
    assert all(meth not in ("create", "action_post") for (_m, meth, _a, _k) in fake.calls)


async def test_crear_asiento_draft_when_auto_post_false(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move", "create"):
            return 201
        return []

    fake = _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_crear_asiento(
        fecha="2023-12-31",
        lineas=[
            {"account_id": 11, "debit": 500.0},
            {"account_id": 22, "credit": 500.0},
        ],
        auto_post=False,
    )
    _assert_envelope(out)
    assert out["data"]["state"] == "draft"
    assert all(meth != "action_post" for (_m, meth, _a, _k) in fake.calls)


async def test_crear_asiento_line_with_both_debit_and_credit_rejected(_configured, monkeypatch):
    fake = _install_fake(monkeypatch, handler=lambda *a: 1)
    out = await odoo.odoo_crear_asiento(
        fecha="2023-12-31",
        lineas=[
            {"account_id": 11, "debit": 100.0, "credit": 100.0},
            {"account_id": 22, "credit": 100.0},
        ],
    )
    _assert_envelope(out)
    assert out["data"]["error"] == "invalid line"
    assert all(meth != "create" for (_m, meth, _a, _k) in fake.calls)


async def test_crear_factura_invalid_move_type(_configured, monkeypatch):
    fake = _install_fake(monkeypatch, handler=lambda *a: 1)
    out = await odoo.odoo_crear_factura_borrador(
        move_type="posted_invoice", partner_id=5, journal_id=2, invoice_date="2026-06-05", lineas=[{}]
    )
    _assert_envelope(out)
    assert out["data"]["error"] == "invalid move_type"
    # no create attempted
    assert all(meth != "create" for (_m, meth, _a, _k) in fake.calls)


async def test_crear_factura_missing_fields(_configured, monkeypatch):
    _install_fake(monkeypatch, handler=lambda *a: 1)
    out = await odoo.odoo_crear_factura_borrador(
        move_type="in_invoice", partner_id=0, journal_id=0, invoice_date="", lineas=[]
    )
    assert out["data"]["error"] == "missing fields"


async def test_crear_partner_reuses_existing_by_cuit(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("res.partner", "search"):
            return [42]  # already exists
        return []

    fake = _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_crear_partner_borrador("Proveedor X", cuit="30111111118")
    _assert_envelope(out)
    assert out["data"]["created"] is False
    assert out["data"]["id"] == 42
    # must NOT have called create
    assert all(meth != "create" for (_m, meth, _a, _k) in fake.calls)


async def test_renombrar_cuenta_happy_path(_configured, monkeypatch):
    captured = {}

    def handler(model, method, args, kwargs):
        if (model, method) == ("account.account", "read"):
            return [{"id": 300, "code": "1.1.1.01.001", "name": "Cash"}]
        if (model, method) == ("account.account", "write"):
            captured["write"] = args  # [[id], vals]
            return True
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_renombrar_cuenta("300", nuevo_nombre="Caja")
    _assert_envelope(out)
    assert out["data"]["changed"] == ["name"]
    assert out["data"]["name"] == "Caja"
    assert out["data"]["before"]["name"] == "Cash"
    # write touched only name
    assert captured["write"][1] == {"name": "Caja"}


async def test_renombrar_cuenta_by_code(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.account", "search"):
            return [300]  # resolved from code
        if (model, method) == ("account.account", "read"):
            return [{"id": 300, "code": "1.1.1.01.001", "name": "Cash"}]
        if (model, method) == ("account.account", "write"):
            return True
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_renombrar_cuenta("1.1.1.01.001", nuevo_nombre="Caja")
    _assert_envelope(out)
    assert out["data"]["name"] == "Caja"


async def test_renombrar_cuenta_not_found(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.account", "search"):
            return []  # code not found
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_renombrar_cuenta("999999", nuevo_nombre="X")
    # 999999 is numeric -> treated as id; read returns [] -> not found
    monkeypatch.setattr  # no-op
    out2 = await odoo.odoo_renombrar_cuenta("NOSUCHCODE", nuevo_nombre="X")
    assert out2["data"]["error"] == "account not found"


async def test_renombrar_cuenta_duplicate_code(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.account", "read"):
            return [{"id": 300, "code": "1.1.1.01.001", "name": "Cash"}]
        if (model, method) == ("account.account", "search"):
            return [999]  # another account already uses the new code
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_renombrar_cuenta("300", nuevo_codigo="411000")
    assert out["data"]["error"] == "duplicate code"


async def test_renombrar_cuenta_nothing_to_change(_configured, monkeypatch):
    _install_fake(monkeypatch, handler=lambda *a: [])
    out = await odoo.odoo_renombrar_cuenta("300")  # no new name/code
    assert out["data"]["error"] == "nothing to change"


async def test_crear_cuenta_refuses_duplicate_code(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.account", "search"):
            return [7]  # code exists
        return []

    fake = _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_crear_cuenta("411000", "Ventas", "income")
    _assert_envelope(out)
    assert out["data"]["created"] is False
    assert all(meth != "create" for (_m, meth, _a, _k) in fake.calls)


# --------------------------------------------------------------------------- #
# odoo_balance_sumas_saldos (trial balance via read_group, read-only)         #
# --------------------------------------------------------------------------- #


async def test_balance_happy_path_cuadra(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move.line", "read_group"):
            return [
                {"account_id": [11, "1.1.01 Caja"], "debit": 1000.0, "credit": 0.0, "balance": 1000.0, "__count": 2},
                {"account_id": [22, "3.1.01 Capital"], "debit": 0.0, "credit": 1000.0, "balance": -1000.0, "__count": 1},
            ]
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_balance_sumas_saldos(desde="2023-01-01", hasta="2023-12-31")
    _assert_envelope(out)
    assert out["data"]["count"] == 2
    assert out["data"]["totales"]["debito"] == 1000.0
    assert out["data"]["totales"]["credito"] == 1000.0
    assert out["data"]["totales"]["cuadra"] is True
    # ordered by account name
    assert out["data"]["cuentas"][0]["account"] == "1.1.01 Caja"


async def test_balance_detects_descuadre(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move.line", "read_group"):
            return [
                {"account_id": [11, "Caja"], "debit": 1000.0, "credit": 0.0, "balance": 1000.0, "__count": 1},
                {"account_id": [22, "Capital"], "debit": 0.0, "credit": 900.0, "balance": -900.0, "__count": 1},
            ]
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_balance_sumas_saldos()
    _assert_envelope(out)
    assert out["data"]["totales"]["cuadra"] is False


async def test_balance_empty_period(_configured, monkeypatch):
    _install_fake(monkeypatch, handler=lambda *a: [])
    out = await odoo.odoo_balance_sumas_saldos(desde="2030-01-01", hasta="2030-12-31")
    _assert_envelope(out)
    assert out["data"]["count"] == 0
    assert out["data"]["totales"]["cuadra"] is True  # 0 == 0


async def test_balance_omits_zero_accounts_by_default(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move.line", "read_group"):
            return [
                {"account_id": [11, "Caja"], "debit": 500.0, "credit": 0.0, "balance": 500.0, "__count": 1},
                {"account_id": [33, "Sin mov"], "debit": 0.0, "credit": 0.0, "balance": 0.0, "__count": 0},
            ]
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_balance_sumas_saldos()
    _assert_envelope(out)
    assert out["data"]["count"] == 1  # the zero account is omitted
    out2 = await odoo.odoo_balance_sumas_saldos(incluir_cero=True)
    assert out2["data"]["count"] == 2


async def test_balance_solo_posteados_filters_domain(_configured, monkeypatch):
    holder = {}

    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move.line", "read_group"):
            return []
        return []

    fake = _install_fake(monkeypatch, handler=handler, obj_holder=holder)
    await odoo.odoo_balance_sumas_saldos(solo_posteados=True)
    # the domain passed to read_group must constrain parent_state to posted
    rg_calls = [a for (m, meth, a, _k) in fake.calls if (m, meth) == ("account.move.line", "read_group")]
    assert rg_calls
    domain = rg_calls[0][0]
    assert ("parent_state", "=", "posted") in domain


async def test_balance_not_configured(monkeypatch):
    monkeypatch.delenv(odoo.URL_ENV, raising=False)
    out = await odoo.odoo_balance_sumas_saldos()
    assert out["data"]["error"] == "odoo not configured"


async def test_balance_unreachable_is_graceful(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        raise xmlrpc.client.Fault(1, "boom")

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_balance_sumas_saldos()
    _assert_envelope(out)
    assert "error" in out["data"]


# --------------------------------------------------------------------------- #
# odoo_reversar_asiento (reverse a posted move)                                #
# --------------------------------------------------------------------------- #


async def test_reversar_posted_move_creates_and_posts_reversal(_configured, monkeypatch):
    holder = {}

    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move", "read"):
            return [{"id": 500, "name": "MV01/2023/0001", "state": "posted", "company_id": [1, "NU"], "move_type": "entry"}]
        if (model, method) == ("account.move", "_reverse_moves"):
            return [777]
        if (model, method) == ("account.move", "action_post"):
            assert args[0] == [777]
            return True
        return []

    _install_fake(monkeypatch, handler=handler, obj_holder=holder)
    out = await odoo.odoo_reversar_asiento(move_id=500, fecha="2023-12-31", motivo="Error de carga")
    _assert_envelope(out)
    assert out["data"]["original_id"] == 500
    assert out["data"]["reversal_id"] == 777
    assert out["data"]["state"] == "posted"
    methods = [(m, meth) for (m, meth, _a, _k) in holder["obj"].calls]
    assert ("account.move", "_reverse_moves") in methods
    assert ("account.move", "action_post") in methods


async def test_reversar_refuses_non_posted_move(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move", "read"):
            return [{"id": 501, "name": "draft", "state": "draft", "company_id": [1, "NU"], "move_type": "entry"}]
        return []

    fake = _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_reversar_asiento(move_id=501)
    _assert_envelope(out)
    assert out["data"]["error"] == "move not posted"
    # never attempted the reversal
    assert all(meth != "_reverse_moves" for (_m, meth, _a, _k) in fake.calls)


async def test_reversar_move_not_found(_configured, monkeypatch):
    _install_fake(monkeypatch, handler=lambda *a: [])
    out = await odoo.odoo_reversar_asiento(move_id=999)
    _assert_envelope(out)
    assert out["data"]["error"] == "move not found"


async def test_reversar_company_mismatch(_configured, monkeypatch):
    monkeypatch.setenv(odoo.COMPANY_ENV, "1")

    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move", "read"):
            return [{"id": 502, "name": "x", "state": "posted", "company_id": [2, "Vastu"], "move_type": "entry"}]
        return []

    fake = _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_reversar_asiento(move_id=502)
    _assert_envelope(out)
    assert out["data"]["error"] == "company mismatch"
    assert all(meth != "_reverse_moves" for (_m, meth, _a, _k) in fake.calls)


async def test_reversar_draft_when_auto_post_false(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move", "read"):
            return [{"id": 503, "name": "x", "state": "posted", "company_id": [1, "NU"], "move_type": "entry"}]
        if (model, method) == ("account.move", "_reverse_moves"):
            return [778]
        return []

    fake = _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_reversar_asiento(move_id=503, auto_post=False)
    _assert_envelope(out)
    assert out["data"]["state"] == "draft"
    assert out["data"]["reversal_id"] == 778
    assert all(meth != "action_post" for (_m, meth, _a, _k) in fake.calls)


async def test_reversar_not_configured(monkeypatch):
    monkeypatch.delenv(odoo.URL_ENV, raising=False)
    out = await odoo.odoo_reversar_asiento(move_id=1)
    assert out["data"]["error"] == "odoo not configured"


# --------------------------------------------------------------------------- #
# LIVE (needs real Odoo + API key). Excluded from CI.                         #
# --------------------------------------------------------------------------- #


@pytest.mark.live
async def test_live_health():
    out = await odoo.odoo_health()
    assert "error" not in out["data"], out["data"]
    assert out["data"]["authenticated"] is True
