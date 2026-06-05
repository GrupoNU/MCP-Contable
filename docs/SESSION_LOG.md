# Session Log — MCP-Contable

> Bitácora de avance por fases. Lo más reciente arriba.

## 2026-06-04 — Fase 3: Managed-agent vencimientos ARCA + recursos estáticos

**Estado:** completada (pendiente checkpoint de Diego antes de Fase 4).

### Recursos estáticos (commit d554092)
- `recursos/monotributo.md`, `calendario-vencimientos-arca.md`, `mapa-rt-facpce.md` + README.
- **Plantillas con fecha de corte, NO valores inventados:** las cifras quedan en `[verify]` hasta
  que alguien las complete desde la fuente oficial con su fecha. Vencida la fecha de corte → `[verify]`.
- Honestidad por diseño: nunca se completan montos/fechas "de memoria".

### Managed-agent `vencimientos-arca` (commit ba17633)
- Monitor de vencimientos ARCA por terminación de CUIT. Plugin de área: `societario-cumplimiento`.
- **Arquitectura de 3 niveles:** reader (sin Write, connectors de lectura) → calculator (cómputo
  puro) → alerta-writer (único con Write). Orquestador solo enruta.
- **Grounding anti-desactualización:** el agente NUNCA afirma una fecha sin un recurso fechado
  vigente o una RG recuperada; si no hay, reporta `[verify]`. Pie de verificación obligatorio.
- Cookbook de Claude API — NO corre en Cowork hoy; no reemplaza al contador.

### Gate Fase 3
- ✅ Los 3 recursos tienen fecha de corte + `[verify]`.
- ✅ El agente no inventa fechas (grounding anti-desactualización en los 4 manifests).
- ✅ Solo `alerta-writer` tiene `write` (isolación de 3 niveles correcta).
- ✅ YAML/JSON válidos.
- ⏸️ Checkpoint con Diego antes de Fase 4.

### Próximo (Fase 4 — cierre)
- Verificación end-to-end, suite global verde, SESSION_LOG final. NO push hasta confirmación de Diego.

---

## 2026-06-04 — Fase 2: Áreas (plugins del estudio)

**Estado:** completada (pendiente checkpoint de Diego antes de Fase 3).

### Plugins construidos (5), todos con commit propio
| Plugin | Rol | Skills | Commit |
|---|---|---|---|
| `impuestos-liquidaciones` | **referencia** (validado por Diego) — IVA, Ganancias, IIBB SF, monotributo, Bs. Personales, retenciones | 4 | 0a4d753 |
| `sueldos` | nómina, cargas sociales, F.931, ART | 4 | e4bda44 |
| `registracion-estados-contables` | asientos, libros, balance, RT FACPCE | 4 | cfb6db8 |
| `societario-cumplimiento` | vencimientos ARCA, regímenes de info, IGJ/RPJEC | 4 | cf3a5d4 |
| `estudio-contable` | **puerta única** (triage + derivación, sin connectors) | 2 | 0fc793d |

### Decisiones validadas por Diego
- Molde aprobado: playbook **sin números hardcodeados** (todo monto/alícuota/fecha se verifica por
  connector o `[verify]`), mapa de riesgo por norma, gates de consecuencias, encabezado conservador.
- **Mismos 4 skills por área** (consistencia): cold-start-interview + consulta-<area> +
  buscar-normativa-<area> + analizar-norma-<area>. La puerta `estudio-contable` tiene 2 (recepcion + cold-start global).

### Construcción
- Plugin de referencia `impuestos-liquidaciones` hecho primero y validado → luego las otras 3 áreas
  en paralelo (3 agentes, carpetas independientes) → por último `estudio-contable`.
- Dominio fiscal verificado de primera mano vía connectors (InfoLEG id 42701 = Dec. 280 IVA t.o.).
  El mapa de riesgo del agente investigador se usó solo para las trampas conceptuales (ARCA=ex-AFIP,
  monotributo semestral, retenciones por RG, proyecto vs vigente, Ley 27.742 laboral ≠ 27.743 fiscal,
  IGJ CABA ≠ RPJEC Santa Fe), NO para números.

### Gate Fase 2
- ✅ **5 plugins** declarados en `marketplace.json`, sin huérfanos; cada uno con plugin.json + playbook + skills.
- ✅ **18 skills user-invocable** en total.
- ✅ **Regla de oro de CLAUDE.md respetada:** 3 de desarrollo (`# CONTEXTO DE DESARROLLO`) + 5 de
  producto (`# PLAYBOOK CONTABLE`); ningún playbook contaminado con convenciones de código.
- ✅ Verificación de dominio de primera mano: ningún playbook hardcodea alícuotas/montos/fechas;
  distinciones críticas presentes (IGJ/RPJEC, 27.742/27.743, marco conceptual/cita RT).
- ⏸️ Checkpoint con Diego antes de Fase 3. (Validación final de cifras/normas = Diego / contador matriculado.)

### Próximo (Fase 3)
- Managed-agent `vencimientos-arca` + recursos estáticos con fecha de corte (monotributo, calendario
  ARCA, mapa RT FACPCE), todos marcados `[verify]`.

---

## 2026-06-04 — Fase 1: Núcleo de fuentes (connectors)

**Estado:** completada (pendiente checkpoint de Diego antes de Fase 2).

### Connectors construidos (7), todos con tests verdes y commit propio
| Connector | Tier | Fuente | Commit | Tests |
|---|---|---|---|---|
| `ckan_nacional` | A | datos.gob.ar (CKAN) | d2f7afa | 15 + 2 live |
| `ckan_juridico` | A | datos.jus.gob.ar (CKAN) — ids de normas fiscales | 897c0d3 | 15 + 2 live |
| `infoleg` | B | InfoLEG verNorma.do (norma por id) | a668c1e | 9 + 1 live |
| `boletin_nacional` | B | Boletín Oficial (RG ARCA) | e8e72e0 | 15 |
| `santafe_sin` | B | SIN SF (Código Fiscal Ley 3456, RG API) | e8c90ca | 16 + 2 live |
| `santafe_fiscal` | B | Calendario impositivo SF (índice por año) | 8bd1de8 | 7 + 1 live |
| `arca` | A | ARCA constancia/padrón vía afip-ws de NU | 72651bd | 14 (+live pend.) |

### Hallazgos verificados de primera mano
- **InfoLEG** responde 200 con UA `MCP-Contable/0.1` pero 403 con UA de navegador → el connector funciona; WebFetch (UA navegador) fallaba. id=423722 = Ley 27801 (smoke).
- **datos.gob.ar** y **datos.jus.gob.ar**: CKAN Action API idéntica, Tier A ✅.
- **Santa Fe SIN** (santafe.gov.ar/normativa): vivo, búsqueda POST de Ley 3456 (Código Fiscal) devuelve resultados.
- **Calendario fiscal SF**: el índice (111353) mapea año→URL oficial; las páginas por año NO exponen los vencimientos en HTML estático → connector honesto (da la URL oficial, no inventa fechas).
- **afip-ws**: NO alcanzable por Tailscale aún (bindea a 127.0.0.1:8001 del VPS, HTTP 000). El connector `arca` quedó construido y testeado con mocks; su live test corre cuando se exponga el servicio (agregar binding `100.88.25.41:8001` al docker-compose del afip-ws, igual que Postgres — cambio en VPS_atmosfera con confirmación de Diego).

### Gate Fase 1
- ✅ **127 tests verdes** (`pytest -m "not live"`); los live verificados por connector contra fuente real.
- ✅ **Security pass:** `import httpx` aparece SOLO en `common/http.py`; ningún connector instancia httpx ni loguea bodies/CUITs → zero-retention preservado.
- ✅ Smoke stdio: los 7 servers FastMCP importan sin error.
- ⏸️ Checkpoint con Diego antes de Fase 2.

### Lección de proceso
- Portar connectors de Legal copiando **bytes crudos con Python** (no PowerShell `-Encoding utf8`, que agrega BOM y altera comillas → rompe cassettes iso-8859-1).

### Próximo (Fase 2)
- Plugin de referencia `impuestos-liquidaciones` (playbook + 4 skills incl. cold-start-interview), validar con Diego, luego replicar a las otras 3 áreas + `estudio-contable` (puerta única).

---

## 2026-06-04 — Fase 0: Fundaciones

**Estado:** completada (pendiente checkpoint de Diego antes de Fase 1).

### Encuadre cerrado con el usuario
- Despliegue: **Claude Cowork** (gemelo del jurídico, no es servicio web).
- Jurisdicción: **Nación (ARCA) + Santa Fe (IIBB, RPJEC)**.
- Perfil NU: **Responsable Inscripto** (IVA + Ganancias).
- Validador: **Diego revisa** (sin matrícula) → encabezado conservador por defecto.
- Área piloto: **impuestos-liquidaciones**, luego replicar a las otras 3.
- Managed-agents: incluir **vencimientos ARCA** desde temprano.
- **5 plugins:** estudio-contable (puerta única) + 4 áreas.

### Investigación de fuentes (verificada de primera mano)
- **ARCA:** sin API pública sin certificado. PERO NU tiene el microservicio **afip-ws** en su VPS
  (cert. de NU, mismo que Odoo, WS `ws_sr_constancia_inscripcion`) → connector `arca` = cliente
  HTTP del afip-ws (Tier A). Plomería Tailscale pendiente (Fase 1).
- **datos.gob.ar** CKAN: Tier A ✅. **datos.jus.gob.ar** CKAN: Tier A ✅ (ids de normas fiscales).
- **InfoLEG** / **Boletín** / **Santa Fe SIN** / **calendario SF**: Tier B (scraping).
- **datos.santafe** CKAN: vacío, no usar. **API SF / RPJEC / DDJJ**: bloqueadas (login).
- **Monotributo / calendario ARCA / RT FACPCE:** recursos estáticos con fecha de corte + `[verify]`.

### Hecho en Fase 0
- Scaffolding: `.gitignore`, `.gitattributes`, `LICENSE`, `README.md`, `QUICKSTART.md`.
- `.claude/settings.json` (deny push/.env/certs; allow uv/pytest/git + WebFetch dominios fiscales).
- 3 CLAUDE.md de **desarrollo** (raíz, connectors, plugins).
- `common/` copiado de Legal → renombrado `mcp_contable` (http/grounding/cache).
- `pyproject.toml` + `.env.example` + `uv sync` (fastmcp, httpx, selectolax, pytest, respx).
- Tests de `common/` adaptados → **36 verdes** (`pytest -m "not live"`).
- Docs base: ARCHITECTURE, GROUNDING, SECURITY, SOURCES, SESSION_LOG.
- `marketplace.json` con los 5 plugins declarados.

### Gate Fase 0
- ✅ `pytest -m "not live"` verde (36).
- ✅ Ningún dato de NU en el repo; credenciales/certs ignorados.
- ⏸️ Checkpoint con Diego antes de Fase 1.

### Próximo (Fase 1)
- Sub-paso 1.0: exponer afip-ws a Tailscale + verificar (`GET /health`).
- Connectors en orden: ckan_nacional → arca → ckan_juridico → infoleg → boletin_nacional →
  santafe_sin → santafe_fiscal. Tests por connector.
