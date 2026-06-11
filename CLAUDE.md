# CONTEXTO DE DESARROLLO — NO es contenido de producto

> ⚠️ Este archivo son **instrucciones para el equipo de agentes que PROGRAMA** MCP-Contable.
> NO confundir con los `CLAUDE.md` de **producto** que viven dentro de cada plugin
> (`plugins/<area>/CLAUDE.md`), que son el playbook contable que lee Claude Cowork.
> Ver `plugins/CLAUDE.md` para la regla de separación completa.

---

## Qué es este proyecto

**MCP-Contable** = "Claude for Legal, versión contable argentina". Un estudio contable de
agentes IA para uso propio de **NU Desarrollos** (Diego revisa; un contador matriculado valida
antes de uso real), extensible a producto. Es el **gemelo contable de MCP-Jurídico**
(`D:\git\MCP-Juridico`), del que se calca la arquitectura y el método (probados).

Arquitectura (calcada del repo oficial verificado `anthropics/claude-for-legal`):
- **UN solo plugin `mcp-contable`** (el repo entero es el plugin). El `marketplace.json` de la
  raíz lo declara con `source: "./plugin"`. Todo el plugin vive en la subcarpeta **`plugin/`**.
- **18 skills** (`plugin/skills/`): una puerta de recepción + 4 áreas (impuestos, sueldos,
  registración, societario), cada una con consulta/buscar/analizar/perfil. El "cerebro" de cada
  área es su `playbook.md` (junto a su skill de consulta).
- **8 connectors MCP en Python** (`plugin/connectors/`, FastMCP, stdio): arca (AFIP vía afip-ws),
  ckan_nacional, ckan_juridico, infoleg, boletin_nacional, santafe_sin, santafe_fiscal, y **odoo**
  (opera la contabilidad de NU en Odoo 18 — circuito contable completo).
- El 90% del valor es **conocimiento contable en Markdown**; el código Python es **solo la
  capa de connectors a datos**.

Despliegue: **Claude Cowork** (principal) / Claude Code. Motor IA = suscripción del usuario ($0).
Accede a carpetas locales de NU + connectors MCP. **Está INSTALADO y operativo en Cowork** (los 8
connectors conectan). Cómo se instala/actualiza y los gotchas de Cowork: ver `docs/COWORK.md`.

### Mapa rápido del repo (para ubicarse al volver)
```
MCP-Contable/                         <- repo = plugin
├─ .claude-plugin/marketplace.json    <- 1 plugin, source "./plugin"
├─ CLAUDE.md (este)  README  QUICKSTART  INSTALL.md
└─ plugin/                            <- EL PLUGIN
   ├─ .claude-plugin/plugin.json  .mcp.json (8 connectors, python directo SIN uv)
   ├─ skills/                        <- 18 skills (recepcion, cold-start, consulta-*, etc.)
   ├─ connectors/                    <- 8 servers FastMCP + tests (.venv pre-creado con uv sync)
   ├─ recursos/                      <- estáticos con fecha de corte (monotributo, calendario, RT)
   ├─ managed-agents/                <- cookbook vencimientos-arca
   └─ docs/                          <- ARCHITECTURE, GROUNDING, SECURITY, SOURCES, COWORK, SESSION_LOG
```

Plan/decisiones: `.claude/plans/`. Docs de dominio y operación: `plugin/docs/`.

## Idioma (regla híbrida)

- **Código Python en inglés**: nombres de módulos, funciones, variables, tools MCP, tests.
- **Contenido contable en español**: plugins, skills (`SKILL.md`), CLAUDE.md de producto,
  docs de dominio. Es contenido para contadores argentinos.
- **Comunicación con el usuario (Diego): español.**
- **Commits en inglés**, formato `tipo(scope): descripción` (feat|fix|docs|refactor|chore|test).

## Stack y herramientas

- **Python 3.12** · gestor **uv** (no pip directo). Venv en `plugin/connectors/.venv`.
- **FastMCP** para los servers MCP, transporte **stdio** (local, sin endpoints expuestos).
- **httpx** para HTTP, **selectolax** para scraping, **xmlrpc.client** para Odoo, **pytest + respx** para tests.
- Un server FastMCP **por fuente** de datos (no monolito): aísla fallos, se testea por separado.
- ⚠️ **En Cowork los connectors NO se lanzan con `uv run`** (uv falla en su sandbox) — el `.mcp.json`
  llama al `python.exe` del `.venv` directo. Ver `docs/COWORK.md`. Para desarrollo local sí se usa
  `uv run` normalmente.

## Reglas de ingeniería (estándar Grupo NU)

- **Testing obligatorio**: nunca se integra código sin test verde. Bug fix = test primero.
  Cada tool MCP tiene tests: happy path, fuente caída (timeout→error grácil), payload vacío,
  y assert de que `source_tier` + `retrieved_at` vienen poblados.
- **Cambios pequeños e incrementales** sobre cambios masivos.
- **NUNCA hacer `git push`** sin confirmación de Diego. NUNCA force push a main.
- **Confirmar antes de cambios destructivos.** Explicar antes de hacer.
- **Commits atómicos** (un cambio lógico por commit).
- Mantener **docs actualizados** cuando se cambia código/config.
- **Versionado (SemVer manual)**: subir `version` en `plugin/.claude-plugin/plugin.json` en
  CADA cambio que se instale en Cowork. `MAYOR.MENOR.PARCHE`: parche (0.3.0→0.3.1) para
  fixes/ajustes; menor (0.3.x→0.4.0) para funcionalidad nueva; mayor (0.x→1.0.0) para "estable
  en producción". Avisar a Diego el número en cada commit. Estado actual: **0.3.0**.

## Grounding anti-alucinación (INNEGOCIABLE — más crítico que en legal)

En contable hay **MONTOS, ALÍCUOTAS, TOPES, VENCIMIENTOS y CATEGORÍAS** que cambian
constantemente (a veces mensual/semestral). Toda tool de connector devuelve
`{data, source_tier, source_url, retrieved_at}`:
- **Tier A** — API oficial estructurada (ARCA vía afip-ws, datos.gob.ar / datos.jus.gob.ar CKAN) → cita usable.
- **Tier B** — scraping de fuente oficial predecible (InfoLEG, Boletín, SIN SF) → marca
  `[scraped — verificar contra fuente oficial]`.
- **Tier C** — sin connector / conocimiento del modelo → marca `[verify]` obligatoria.

Lógica central en `connectors/src/mcp_contable/common/grounding.py`. **Toda salida es un
borrador para revisión de un contador matriculado.** Nunca afirmar un monto/alícuota/categoría/
vencimiento sin `retrieved_at` reciente. Distinguir **proyecto** de **norma vigente**.

## Confidencialidad / zero-retention

- `common/http.py` **NUNCA loguea request/response bodies** (ni params, headers, ni URL completa).
- Los `logs/` de los plugins registran **solo metadata** (tool, timestamp, source_tier) —
  nunca contenido contable de NU.
- Sin telemetría saliente. Detalles en `docs/SECURITY.md`.
- **Credenciales (certificado ARCA, API key de Odoo, claves):** viven **fuera del repo**.
  - `arca` NO maneja el certificado: reusa el microservicio `afip-ws` del VPS por HTTP.
  - `odoo` lee su API key de `~/.mcp-contable/secrets.env` (archivo local, gitignored, fuera del
    repo) — porque el sandbox de Cowork NO hereda las env vars del sistema. Ver `docs/COWORK.md`.

## Cómo trabaja el equipo

Diego es Director. Claude (orquestador) es Tech Lead — coordina agentes, **no codea
directo lo que puede delegar**. Los agentes implementan dentro de su scope.
- Paralelismo **conservador**: fundaciones primero (validadas), luego equipos en paralelo.
- Checkpoints **por fase**.
- Validación contable: **agente verifica cifras/normas contra fuentes + Diego/contador final**.

## Comandos útiles

```bash
cd plugin/connectors
uv sync                       # crear/actualizar .venv (necesario: Cowork usa este venv directo)
uv run pytest -m "not live"   # tests sin pegar a APIs reales (CI) — 143+ tests
uv run pytest                 # incluye tests @live (pegan a fuentes reales / Odoo)
uv run python -m mcp_contable.odoo.server   # correr un server (smoke stdio)
claude plugin validate ./plugin   # validar el plugin (marketplace + plugin)
```

## Al volver a trabajar en este repo (checklist mental)

1. Es **un plugin único** en `plugin/`. El `.mcp.json` usa **python directo (sin uv)** por el
   sandbox de Cowork — ver `docs/COWORK.md` antes de tocar el `.mcp.json`.
2. Tras instalar/clonar: `cd plugin/connectors && uv sync` (crea el `.venv` que Cowork usa).
3. Credenciales sensibles NO van al repo: certificado AFIP en el VPS (afip-ws), API key de Odoo en
   `~/.mcp-contable/secrets.env`.
4. Para actualizar el plugin en Cowork tras un push: Customize → Plugins → "..." → Buscar
   actualizaciones → Actualizar → **reiniciar Cowork**. Lecciones y errores comunes: `docs/COWORK.md`.
5. Estado y decisiones de cada sesión: `docs/SESSION_LOG.md`. Infra de Odoo: `docs/ODOO.md` (si existe)
   o las notas de memoria.
