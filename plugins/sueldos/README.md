# Plugin: Sueldos y Nómina (Argentina — Nación + Santa Fe)

Plugin de **MCP-Contable** para el área de **sueldos y nómina**. Asiste a NU Desarrollos
(Responsable Inscripto, empleadora) en consultas sobre liquidación de haberes, conceptos
remunerativos/no remunerativos, cargas sociales (aportes y contribuciones), F.931, ART, convenios
colectivos, SAC, vacaciones e indemnizaciones, con **grounding** contra fuentes oficiales y
**gates** de revisión profesional.

## Qué hace

- **Configura un perfil de trabajo** (rol, entidad/CUIT empleador, régimen, jurisdicciones, convenio
  colectivo, ART, dotación, carpetas locales) vía entrevista de inicio (`cold-start-interview`), que
  personaliza el playbook del plugin.
- **Responde consultas de nómina generales** (`consulta-sueldos`) aplicando el playbook y las reglas
  de grounding.
- **Busca normativa laboral/previsional** (`buscar-normativa-laboral`) usando connectors oficiales:
  - `arca` → constancia/padrón del CUIT del empleador (vía afip-ws de NU).
  - `ckan-juridico` / `ckan-nacional` → datasets; hallar el id de InfoLEG de una norma laboral.
  - `infoleg` → recuperar una norma nacional por id (LCT, SIPA, Asignaciones, ART, Ley Bases).
  - `boletin-nacional` → RG de ARCA / Decretos / Resoluciones de seguridad social (alícuotas, topes).
  - `santafe-sin` → normativa fiscal/laboral provincial de Santa Fe.
  - `santafe-fiscal` → calendario impositivo de Santa Fe (URL oficial por año).
- **Analiza una norma puntual** (`analizar-norma-laboral`): la recupera por id/número y produce un
  resumen-borrador.

### Áreas cubiertas (con grounding obligatorio)

- LCT (Ley 20.744) — relación laboral, conceptos remunerativos/no remunerativos, SAC, vacaciones,
  indemnizaciones (montos/topes siempre verificados).
- Cargas sociales — aportes (trabajador) y contribuciones (empleador): SIPA (Ley 24.241), INSSJP/PAMI,
  Obra Social, ANSSAL, Asignaciones Familiares (Ley 24.714), Fondo Nacional de Empleo.
  **Alícuotas y topes de la base imponible siempre verificados** (cambian por Dec./RG ARCA y movilidad).
- F.931 (DDJJ de seguridad social ante ARCA) — qué es y cómo se compone; **sin montos inventados**.
- ART (Ley 24.557) — marco; **la alícuota la fija la aseguradora**, no se afirma.
- Convenios colectivos (CCT) — **escalas salariales siempre verificadas** (acuerdos paritarios).
- Reforma laboral 2024-2026 (Ley 27.742 — Ley Bases) — distinguiendo vigente de proyecto, sin
  confundir con la reforma fiscal (Ley 27.743).

## Qué NO hace

- **No da asesoramiento contable, laboral ni previsional.** Toda salida es un **borrador para
  revisión de un contador matriculado**, que verifica las cifras y asume la responsabilidad.
- **No afirma alícuotas, topes de base imponible, mínimos, asignaciones familiares, escalas de CCT
  ni alícuotas de ART** sin un resultado de connector con `retrieved_at`. Sin fuente → `[verify]`.
- **No transcribe una escala salarial de convenio ni una tabla de asignaciones de memoria** (cambian
  por paritaria / movilidad).
- **No inventa el cálculo ni los montos del F.931** (surgen de la liquidación y de las alícuotas vigentes).
- **No presenta una reforma/proyecto laboral como vigente** sin verificar su entrada en vigor.
- **No liquida sueldos para pago, emite recibos, presenta F.931 ni calcula indemnizaciones finales**
  sin confirmación del usuario y revisión profesional.

## Skills

| Skill | Invocación | Qué hace |
|---|---|---|
| `cold-start-interview` | `/sueldos:cold-start-interview` | Entrevista de configuración del perfil. |
| `consulta-sueldos` | `/sueldos:consulta-sueldos` | Responde una consulta de nómina/cargas sociales general. |
| `buscar-normativa-laboral` | `/sueldos:buscar-normativa-laboral` | Busca normativa/RG/calendario con los connectors. |
| `analizar-norma-laboral` | `/sueldos:analizar-norma-laboral` | Recupera y resume una norma por id/número. |

## Connectors (MCP) — ver `.mcp.json`

Se ejecutan por stdio con `uv run --directory <connectors>`. Las rutas en `.mcp.json` son
**absolutas a la carpeta `connectors` de este repo en esta máquina** — ajustarlas si la instalación
difiere (lección de MCP-Juridico). El connector `arca` requiere `AFIP_WS_BASE_URL` configurado
(afip-ws de NU, accesible por Tailscale).

## Configuración persistida

El perfil personalizado se guarda en:
`~/.claude/plugins/config/mcp-contable/sueldos/CLAUDE.md`

## Aviso

Herramienta de asistencia. **No reemplaza el criterio de un contador público matriculado.** Toda
salida es un borrador sujeto a revisión profesional. Autor: **Grupo NU**.
