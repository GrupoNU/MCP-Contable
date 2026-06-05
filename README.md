# MCP-Contable

> **Estudio contable de agentes IA para la gestión contable/impositiva argentina** — uso propio
> de **NU Desarrollos**, replicando el molde probado de su gemelo **MCP-Jurídico** (que a su vez
> calca el patrón oficial de *Claude for Legal* de Anthropic).

MCP-Contable es un **marketplace local de plugins contables** (en Markdown, español) +
**connectors MCP en Python** (FastMCP, stdio) a fuentes fiscales/contables argentinas. Corre
en **Claude Cowork / Claude Code** usando la suscripción Claude del propio usuario (costo IA
$0). Claude accede a las **carpetas locales** de NU Desarrollos (facturas, papeles de trabajo,
DDJJ) + las fuentes oficiales vía los connectors.

## Arquitectura

Es **un solo plugin** (`mcp-contable`) que trae todo el estudio. El repo es a la vez el plugin: el
`marketplace.json` lo declara con `source: "./"`.

- **`skills/`** — los 18 skills del estudio (Markdown, español):
  - `recepcion` — **puerta única**: clasifica la consulta y deriva al área correcta.
  - `cold-start-interview` — perfil global del estudio (rol, CUIT, régimen, jurisdicciones).
  - **Impuestos:** `consulta-impuestos` (+ su `playbook.md`), `buscar-normativa-fiscal`,
    `analizar-norma-fiscal`, `perfil-impuestos`. IVA, Ganancias, IIBB, monotributo, retenciones.
  - **Sueldos:** `consulta-sueldos` (+ playbook), `buscar-normativa-laboral`, `analizar-norma-laboral`,
    `perfil-sueldos`. Nómina, cargas sociales, F.931, ART.
  - **Registración:** `consulta-registracion` (+ playbook), `buscar-normativa-contable`,
    `analizar-norma-contable`, `perfil-registracion`. Asientos, libros, balance, RT FACPCE.
  - **Societario:** `consulta-cumplimiento` (+ playbook), `buscar-normativa-societaria`,
    `analizar-norma-societaria`, `perfil-societario`. Vencimientos ARCA, regímenes, IGJ/RPJEC.
- **`.mcp.json`** (raíz) — declara los 7 connectors con `${CLAUDE_PLUGIN_ROOT}/connectors`.
- **`connectors/`** — servers FastMCP (Python, código en inglés) a fuentes oficiales: ARCA
  (vía microservicio afip-ws), datos.gob.ar / datos.jus.gob.ar (CKAN), InfoLEG, Boletín
  Oficial, Santa Fe (SIN, calendario fiscal).
- **`recursos/`** — estáticos versionados con **fecha de corte** (tabla de monotributo,
  calendario ARCA, mapa de RT FACPCE), siempre marcados `[verify]`.
- **`managed-agents/`** — agentes recurrentes (ej. alertas de vencimientos ARCA).
- **`docs/`** — ARCHITECTURE, GROUNDING, SECURITY, SOURCES, SESSION_LOG.

## Grounding anti-alucinación (innegociable)

En contable el riesgo nº1 es presentar un **monto/alícuota/tope/vencimiento desactualizado**
como vigente. Por eso:

- Toda tool de connector devuelve `{data, source_tier, source_url, retrieved_at}`.
- **Tier A** (API oficial: ARCA/afip-ws, CKAN) → cita usable.
- **Tier B** (scraping oficial: InfoLEG, Boletín, SIN SF) → `[scraped — verificar contra fuente oficial]`.
- **Tier C** (sin connector / memoria del modelo) → `[verify]` obligatorio.
- **Nunca** se afirma una cifra/alícuota/categoría/vencimiento sin `retrieved_at` reciente.
- **Toda salida es un borrador para revisión de un contador matriculado.**

## Instalación

Para instalar el estudio en **Claude Cowork / Claude Code**, ver **[INSTALL.md](INSTALL.md)**
(guía paso a paso para el usuario). Para desarrollo (tests, etc.), ver [QUICKSTART.md](QUICKSTART.md).

Resumen: en Cowork → Customize → Plugins → Add from a repository → URL del repo → Install
`mcp-contable` → `/mcp-contable:cold-start-interview`.

## Estado

✅ **Fases 0-4 completadas + connector `arca` operativo** (2026-06-04). Repo funcional: 7 connectors
(127 tests verdes), 1 plugin `mcp-contable` (18 skills), 3 recursos estáticos y el managed-agent
`vencimientos-arca`. Listo para instalar en Cowork desde GitHub (valida con `claude plugin validate`).

**Pendientes de coordinación (no bloquean el repo):**
- Exponer el microservicio `afip-ws` del VPS a la red Tailscale para activar el connector `arca`
  en vivo (cambio de infra en VPS_atmosfera).
- Validación de cifras/normas por un contador matriculado (gate de dominio).
- Prueba de instalación del marketplace en Claude Cowork.

Ver `docs/SESSION_LOG.md` para el detalle por fases.

## Aviso

Herramienta de asistencia. **No reemplaza el criterio de un contador público matriculado.**
Toda salida es un borrador sujeto a revisión profesional. Autor: **Grupo NU**.
