# Session Log — MCP-Contable

> Bitácora de avance por fases. Lo más reciente arriba.

## 2026-06-11 — Convivencia con el gemelo MCP-Jurídico: renombrado + versionado

**Objetivo:** evitar la colisión de nombres de skill con el gemelo MCP-Jurídico (ambos
instalados a nivel user en Cowork).

**Hecho:**
- **Colisión resuelta:** ambos gemelos compartían `recepcion` y `perfil-societario`, lo que
  hacía `/recepcion` ambiguo. Renombrado en este repo: **`recepcion → contabilidad`** (puerta
  única ahora `/contabilidad`) y **`perfil-societario → perfil-societario-contable`**.
  Referencias internas actualizadas (docs, playbook, consulta-cumplimiento). **Cero colisiones**
  con el jurídico (verificado: 18 nombres del contable vs 29 del jurídico, intersección vacía).
- **Versionado SemVer manual adoptado:** `0.1.0 → 0.3.0`. Regla documentada en `CLAUDE.md`:
  subir `version` en `plugin/.claude-plugin/plugin.json` en cada cambio instalable en Cowork.

**Puertas de entrada finales:** `/contabilidad` (este estudio) · `/juridico` (el gemelo legal).

---

## 2026-06-06 — Connector Odoo + instalación operativa en Cowork (circuito completo)

**Estado:** ✅ **COMPLETADO. El estudio está instalado y operativo en Cowork con los 8 connectors.**

### Connector `odoo` (8º connector) — opera la contabilidad de NU
- 8 tools de lectura (health, company, plan_cuentas, impuestos, diarios, partners, comprobantes,
  l10n_ar) + 3 de escritura **en borrador** (partner, cuenta, factura). **NUNCA contabiliza**
  (`action_post` no se llama; eso es acción humana en Odoo). Scope a `ODOO_COMPANY_ID` (NU id=1, no Vastu).
- API XML-RPC de Odoo 18, auth por API key del usuario dedicado `mcp-contable`. 16 tests + live.
- Verificado en vivo: NU Desarrollos Conscientes S.R.L., 308 cuentas (plan estándar RI en inglés — a
  adaptar), l10n_ar instalado. El plan de cuentas existe pero NUNCA se cargaron comprobantes → ese es
  el trabajo que sigue (IVA atrasado, balances, DDJJ).

### Seguridad de Odoo (antes de conectar — riesgo detectado por Diego)
- Odoo corría con `list_db=True` (gestor de bases accesible → se podía borrar la base). Se hizo
  **backup** + `odoo.conf` con `list_db=False`, master password fuerte, `proxy_mode`, `dbfilter`.
  Datos/certificado AFIP intactos. Dominio real: `odoo.gruponu.com` (por Tailscale; no expuesto a
  internet). Repo VPS_atmosfera sincronizado con prod.

### Instalación en Cowork — cadena de problemas resueltos (ver `docs/COWORK.md`)
Repo privado→público (#28125) · `source:"./"`→`./plugin` · skills con `name:` duplicado · **`uv` no
funciona en el sandbox de Cowork** (→ python directo del venv, sin uv) · **el sandbox no hereda env
vars de Windows** (→ el connector odoo lee `~/.mcp-contable/secrets.env`, fuera del repo).
**Resultado: los 8 connectors conectan y odoo autentica.**

### Aprendizaje de proceso
- El chat de Cowork da diagnósticos genéricos/equivocados; **el error real está en los logs**
  (`mcp-logs-plugin-mcp-contable-<x>/*.jsonl` y `cowork_host_loop_debug.log`). Reproducir el arranque
  local desde el cwd contaminado antes de pushear cada fix.

---

## 2026-06-04 — Reestructura: 5 plugins → 1 plugin único (para instalar en Cowork)

**Por qué:** al preparar la instalación en Cowork se descubrieron dos límites reales (verificados en
la doc oficial de Claude Code):
1. **Cowork instala marketplaces solo desde un repo Git (GitHub), no desde carpeta local.**
2. **Un plugin instalado no puede referenciar archivos fuera de su carpeta** (path traversal: rutas
   `../connectors` "will not work after installation because those external files are not copied to
   the cache"). Con `connectors/` compartido en la raíz, los 5 plugins separados no lo resolvían
   post-install. Los **symlinks no son viables en Windows** (git los materializa como carpetas →
   probado y descartado).

**Solución:** consolidar todo en **un solo plugin `mcp-contable`** (el repo raíz = el plugin).
- `marketplace.json`: 1 plugin, `source: "./"`. `plugin.json` en `.claude-plugin/`.
- `.mcp.json` en la raíz con **`${CLAUDE_PLUGIN_ROOT}/connectors`** para los 7 servers (la variable la
  expande Cowork a la ruta de instalación real — verificado en doc + smoke test).
- **18 skills** consolidados en `skills/`. Los cold-start de área se renombraron a `perfil-<area>`;
  el global queda `cold-start-interview`. Cada playbook de área viaja como
  `skills/consulta-<area>/playbook.md` (lo lee su skill).
- Referencias internas reescritas a `/mcp-contable:<skill>` y nuevas rutas de perfil. `plugins/`
  eliminada; `plugins/CLAUDE.md` (desarrollo) preservado como `docs/DEVELOPING-SKILLS.md`.
- INSTALL.md/README reescritos para el flujo **Cowork desde GitHub** (Customize → Plugins → Add from
  a repository).
- Hecho en rama `single-plugin`, validado (`claude plugin validate` passed; 18 skills OK; connector
  arranca con `${CLAUDE_PLUGIN_ROOT}`; **127 tests verdes**), mergeado a `main`.

**Requisito de entorno verificado en esta PC:** uv 0.9.11 + Python 3.12.9 en PATH (`C:\Users\grupo\
.local\bin`), `.venv` con deps. Cowork lanza `uv` por nombre → lo encuentra.

---

## 2026-06-04 — Post-cierre: connector `arca` operativo (certificado AFIP probado)

**Tarea externa (infra VPS), completada con aprobación de Diego.**

- **Certificado AFIP de NU probado de primera mano:** desde el VPS, `GET /fiscal/cuit/30717928993`
  devolvió el padrón real → **NU DESARROLLOS CONSCIENTES S.R.L.**, ACTIVO, JURÍDICA, Piñero (Santa Fe).
  El cert. `afip.crt`/`afip.key` (montado en `/opt/afip-ws/certs`, AFIP_ENV=prod) funciona contra el
  WS `ws_sr_constancia_inscripcion`.
- **afip-ws expuesto a Tailscale:** se agregó el binding `100.88.25.41:8001:8000` al
  `docker-compose.yml` del afip-ws (backup previo; `docker compose config` validado; recreado con
  `up -d`). Mismo patrón que supabase-postgres. No expuesto a internet (UFW no abre el puerto).
  El cambio se reflejó también en el repo `VPS_atmosfera` (shared-services/afip-ws/docker-compose.yml).
- **Connector `arca` operativo end-to-end:** alcanzable desde esta PC por Tailscale (`/health` HTTP
  200); live test de `arca` verde; `AFIP_WS_BASE_URL=http://100.88.25.41:8001` en `connectors/.env`
  (gitignored). Docs actualizadas (ARCHITECTURE, SOURCES, .env.example).

---

## 2026-06-04 — Fase 4: Cierre

**Estado:** completada. **Fases 0-4 del plan terminadas.**

### Verificación end-to-end
- ✅ **Suite global: 127 tests verdes** (`pytest -m "not live"`); los 7 servers FastMCP importan OK.
- ✅ **Inventario estructural coherente:** marketplace con 5 plugins (18 skills user-invocable),
  7 connectors (+ 3 test files de common/ = 10 en total), 3 recursos estáticos + README,
  1 managed-agent, 5 docs.
- ✅ **Security pass final (zero-retention):** `import httpx` solo en `common/http.py`; ningún
  `.env`/certificado/clave versionado (solo `.env.example`); `settings.local.json` gitignored;
  ningún CUIT/monto real de NU (solo los ficticios de test); `http.py` conserva sus marcadores
  zero-retention.
- ✅ **Regla de oro de CLAUDE.md:** 3 de desarrollo + 5 de producto, sin contaminación cruzada.

### Resumen del proyecto (Fases 0-4)
| Fase | Entregable | Commits clave |
|---|---|---|
| 0 | Fundaciones (common/ + docs + marketplace) | b10a77b |
| 1 | 7 connectors (Tier A/B), 127 tests | d2f7afa…72651bd |
| 2 | 5 plugins del estudio (18 skills) | 0a4d753…0fc793d |
| 3 | recursos estáticos + managed-agent vencimientos-arca | d554092, ba17633 |
| 4 | cierre (verificación end-to-end) | (este) |

### Pendientes de coordinación (NO bloquean el repo; tareas externas)
1. **Exponer `afip-ws` a Tailscale** (cambio en VPS_atmosfera: agregar binding `100.88.25.41:8001`
   al docker-compose del afip-ws, como Postgres) → activa el connector `arca` en vivo + su live test.
2. **Validación de cifras/normas por un contador matriculado** (gate de dominio del kickoff).
3. **Prueba de instalación del marketplace en Claude Cowork** (validar rutas `.mcp.json` reales).

### NO push
- Todo commiteado en `main`, **sin push** — esperando confirmación de Diego.

---

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
  buscar-normativa-<area> + analizar-norma-<area>. La puerta `estudio-contable` tiene 2 (contabilidad + cold-start global).

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
