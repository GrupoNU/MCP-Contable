# Plan de mejora — Conector Odoo: generación de balances para Cowork

> **Autor:** Claude (sesión 2026-06-06, repo VPS_atmosfera) + Diego
> **Estado:** PARCIALMENTE IMPLEMENTADO — `odoo_balance_sumas_saldos` (3.1) ✅ hecho con tests.
>            `odoo_libro_mayor` (3.2) y `odoo_estado_resultados` (3.3) quedan pendientes.
> **Área:** `plugin/connectors/src/mcp_contable/odoo/server.py`
> **Convenciones:** hereda `connectors/CLAUDE.md` (Tier A, grounding, draft-only, tests obligatorios)

---

## 1. Contexto y motivación

El conector Odoo actual (Fase 1 READ + Fase 2 WRITE-draft) expone lectura de datos **crudos**:
plan de cuentas, impuestos, diarios, partners y comprobantes (`account.move`). Pero **no tiene
ninguna tool que produzca un BALANCE** (saldos agregados por cuenta).

Hoy (2026-06-06) en el Odoo de NU se instaló el módulo OCA `account_financial_report`, que agrega
los reportes financieros a la **UI de Odoo** (Balance de Sumas y Saldos, Libro Mayor, etc.). Pero
esos reportes son **wizards de la UI** — no se exponen por XML-RPC de forma simple, y NO conviene
depender de ellos.

**Objetivo:** que Cowork pueda pedir "armame el balance de sumas y saldos del año X" y el conector
lo devuelva como datos estructurados (grounded Tier A), sin depender del wizard OCA.

## 2. Decisión de diseño clave

**NO ejecutar el reporte OCA por RPC. Calcular el balance directamente desde `account.move.line`.**

Razones:
- El motor contable (partida doble) vive en `account.move.line` — toda línea de asiento tiene
  `account_id`, `debit`, `credit`, `balance`, `date`, `parent_state`. Es la fuente de verdad.
- `read_group` (método estándar de Odoo, disponible por XML-RPC) agrupa y suma del lado del servidor
  en una sola llamada — eficiente y robusto.
- Independiente de que `account_financial_report` esté instalado o no. Si mañana se desinstala el
  módulo OCA, la tool sigue funcionando.
- El "Balance de Sumas y Saldos" (Trial Balance) ES exactamente: por cada cuenta, suma de débitos,
  suma de créditos, y saldo. Eso es un `read_group` sobre `account.move.line`.

## 3. Tools a agregar (Fase 3: REPORTES, read-only)

Todas read-only (cero riesgo), grounded Tier A, scoped a `ODOO_COMPANY_ID`.

### 3.1 `odoo_balance_sumas_saldos` (PRIORITARIA) ✅ IMPLEMENTADO 2026-06-06

Trial Balance: por cuenta, débito/crédito/saldo acumulado en un rango de fechas.

**Firma:**
```python
async def odoo_balance_sumas_saldos(
    desde: str = "",          # YYYY-MM-DD (inclusive)
    hasta: str = "",          # YYYY-MM-DD (inclusive)
    solo_posteados: bool = True,   # True = solo state=posted (balance "real")
    incluir_cero: bool = False,    # incluir cuentas sin movimiento en el período
) -> dict[str, Any]
```

**Lógica (pseudocódigo siguiendo el patrón `_execute`/`_ok`):**
```python
if not _cfg()["url"]:
    return _not_configured_error("odoo_balance_sumas_saldos")

domain = _company_domain()                      # ("company_id","=",cid) — move.line SÍ tiene company_id
if desde:  domain += [("date", ">=", desde)]
if hasta:  domain += [("date", "<=", hasta)]
if solo_posteados:
    domain += [("parent_state", "=", "posted")] # parent_state = estado del account.move padre
else:
    domain += [("parent_state", "in", ["posted", "draft"])]
# nota: excluir cuentas off-balance si hiciera falta -> ("account_id.account_type","!=","off_balance")

rows, err = _execute(
    "account.move.line", "read_group",
    [domain],                                    # args[0] = domain
    {
        "fields": ["debit:sum", "credit:sum", "balance:sum"],
        "groupby": ["account_id"],
        "lazy": False,
    },
)
if err is not None:
    return err

# read_group devuelve, por grupo: {"account_id":[id,name], "debit":x, "credit":y, "balance":z, "__count":n}
lineas = []
for r in (rows or []):
    acc = r.get("account_id") or [None, None]
    deb = round(r.get("debit") or 0.0, 2)
    cre = round(r.get("credit") or 0.0, 2)
    sal = round(r.get("balance") or 0.0, 2)
    if not incluir_cero and deb == 0.0 and cre == 0.0:
        continue
    lineas.append({
        "account_id": acc[0],
        "account": acc[1],          # "1.1.01 Caja" (code+name)
        "debito": deb,
        "credito": cre,
        "saldo": sal,
        "movimientos": r.get("__count"),
    })

lineas.sort(key=lambda x: (x["account"] or ""))
tot_deb = round(sum(l["debito"] for l in lineas), 2)
tot_cre = round(sum(l["credito"] for l in lineas), 2)
cuadra = abs(tot_deb - tot_cre) < 0.01   # control de partida doble

return _ok(
    {
        "periodo": {"desde": desde or None, "hasta": hasta or None},
        "solo_posteados": solo_posteados,
        "cuentas": lineas,
        "totales": {"debito": tot_deb, "credito": tot_cre, "cuadra": cuadra},
        "count": len(lineas),
    },
    "account.move.line",
    notes="Balance de sumas y saldos (trial balance) calculado desde move.line via read_group.",
)
```

**Por qué importa `cuadra`:** en partida doble, total débito = total crédito siempre. Devolverlo
deja que Cowork detecte de inmediato si hay asientos descuadrados (útil durante la migración de 3 años).

### 3.2 `odoo_libro_mayor` (cuenta específica)

Movimientos detallados de UNA cuenta en un rango (para auditar/explicar un saldo).

**Firma:**
```python
async def odoo_libro_mayor(
    account_code: str,        # ej "1.1.01" — se resuelve a account_id
    desde: str = "",
    hasta: str = "",
    solo_posteados: bool = True,
    limit: int = 200,
) -> dict[str, Any]
```
Resuelve `account.account` por `code` (con `_account_company_domain`), luego `account.move.line.read`
con domain `("account_id","=",id)` + fechas + `parent_state`. Devuelve cada línea con
`{date, move_name, partner, debit, credit, balance, ref}` ordenadas por fecha. Incluir saldo corriente
(running balance) calculado en Python.

### 3.3 `odoo_estado_resultados` (opcional, fase posterior)

Igual que el trial balance pero filtrando `account_id.account_type` a las cuentas de resultado
(`income*`, `expense*`) y devolviendo el resultado neto del período. El Balance General
(situación patrimonial) usa los `asset*`/`liability*`/`equity*`. Se puede derivar todo del mismo
`read_group` agregando `account_type` al `groupby`.

> **Recomendación:** implementar 3.1 primero (cubre el 80% de lo que Cowork necesita), luego 3.2,
> y 3.3 solo si se pide explícitamente.

## 4. Convenciones a respetar (de `connectors/CLAUDE.md`)

- ✅ Nombre `odoo_<accion>` en inglés/español consistente con las tools existentes (`odoo_get_*`).
  Sugerencia: mantener prefijo `odoo_` y nombres descriptivos (`odoo_balance_sumas_saldos`).
- ✅ Toda tool devuelve `_ok(...)` = `to_dict(ground(data, TIER, _source_url(...)))`. Nunca data cruda.
- ✅ Todo RPC pasa por `_execute(...)` (auth centralizada + manejo grácil de Fault/timeout). **Prohibido**
  llamar a `models.execute_kw` directo en la tool.
- ✅ Errores gráciles: si Odoo no responde, la tool devuelve `_error(...)`, nunca explota.
- ✅ Read-only → Fase 3 es **cero riesgo** (no escribe nada, no necesita el gate de confirmación).
- ✅ Scoping multi-compañía: usar `_company_domain()` (move.line tiene `company_id`) — NO mezclar NU/Vastu.

## 5. Testing (obligatorio — regla Grupo NU)

`pytest + respx` no aplica acá (XML-RPC, no httpx). Seguir el patrón de `tests/test_odoo.py`:
mockear `_execute` / el `ServerProxy`. Cobertura mínima por tool nueva:
- **happy path:** `read_group` devuelve grupos → balance correcto + `cuadra=True`.
- **período vacío:** sin movimientos → `cuentas=[]`, totales en 0, `cuadra=True`.
- **descuadre:** débito ≠ crédito → `cuadra=False` (asegura que el control funciona).
- **Odoo unreachable / Fault:** tool devuelve `_error`, no explota.
- **assert grounding:** `source_tier` + `retrieved_at` poblados en el resultado.
- Tests live (contra el Odoo real) → `@pytest.mark.live`, excluidos de CI.

## 6. Verificación funcional (smoke test post-deploy)

Con datos reales del Odoo de NU (tras cargar los comprobantes de los 3 años):
1. `odoo_balance_sumas_saldos(desde="2023-01-01", hasta="2023-12-31")` → comparar `totales.debito`
   y `totales.credito` contra el "Balance de Sumas y Saldos" generado en la UI de Odoo
   (Facturación → Reportes → Informes de contabilidad OCA → Balance de Sumas y Saldos, mismo período).
   **Deben coincidir** (es la validación de que el cálculo por move.line == reporte OCA).
2. `cuadra` debe ser `True` para cualquier período (si da `False`, hay asientos descuadrados → revisar).

## 7. Alcance explícito (qué NO hace)

- NO postea ni modifica nada (read-only).
- NO genera el PDF/Excel del reporte OCA — devuelve datos estructurados que Cowork formatea.
- NO reemplaza el reporte de la UI de Odoo para presentación formal/legal — es para que Cowork
  razone sobre los números y los presente en conversación.

---

## Resumen para el equipo del conector

Agregar **1 tool prioritaria** (`odoo_balance_sumas_saldos`) que calcula el trial balance vía
`account.move.line.read_group` — independiente del módulo OCA, grounded Tier A, read-only, con
control de cuadre de partida doble. Opcionalmente `odoo_libro_mayor` y `odoo_estado_resultados`
después. Tests con el patrón de `test_odoo.py` + validación cruzada contra el reporte de la UI.
