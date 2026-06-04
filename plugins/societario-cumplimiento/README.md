# Plugin: Societario y Cumplimiento (Argentina — Nación + Santa Fe)

Plugin de **MCP-Contable** para el área de **cumplimiento societario y registral**. Asiste a NU
Desarrollos (Responsable Inscripto) en el calendario de vencimientos de ARCA, los regímenes de
información, las presentaciones societarias (Ley General de Sociedades 19.550) y los trámites
registrales por jurisdicción (IGJ en CABA / RPJEC en Santa Fe), con **grounding** contra fuentes
oficiales y **gates** de revisión profesional.

## Qué hace

- **Configura un perfil de trabajo** (rol, entidad/CUIT, tipo societario, régimen, jurisdicciones,
  jurisdicción registral, terminación de CUIT, regímenes aplicables, carpetas locales) vía entrevista
  de inicio (`cold-start-interview`), que personaliza el playbook del plugin.
- **Responde consultas de cumplimiento** (`consulta-cumplimiento`) aplicando el playbook y las reglas
  de grounding (vencimientos ARCA, regímenes de información, obligaciones societarias y registrales).
- **Busca normativa societaria y de cumplimiento** (`buscar-normativa-societaria`) usando connectors
  oficiales:
  - `arca` → constancia/padrón de un CUIT (vía afip-ws de NU).
  - `ckan-juridico` / `ckan-nacional` → datasets; hallar el id de InfoLEG de una norma (p. ej. LGS 19.550).
  - `infoleg` → recuperar una norma nacional por id.
  - `boletin-nacional` → RG de ARCA (calendario anual de vencimientos, regímenes de información).
  - `santafe-sin` → normativa registral/fiscal de Santa Fe (incl. marco del RPJEC).
  - `santafe-fiscal` → calendario impositivo de Santa Fe (URL oficial por año).
- **Analiza una norma puntual** (`analizar-norma-societaria`): la recupera por id/número y produce un
  resumen-borrador.

### Áreas cubiertas (con grounding obligatorio)

- **Calendario de vencimientos ARCA** — impositivos y de seguridad social por terminación de CUIT.
  **Las fechas se verifican siempre** (cambian cada año por RG): recurso estático fechado o RG del Boletín.
- **Regímenes de información ARCA** (participaciones societarias, CITI, otros) — **vigencia y plazos
  siempre verificados** (se crean/suspenden/derogan por RG).
- **Ley General de Sociedades 19.550** — marco (tipos societarios, obligaciones de los administradores),
  citable por InfoLEG, distinguiendo vigente de proyecto de reforma.
- **Presentación de estados contables ante el registro** — marco; plazos/requisitos por jurisdicción.
- **Trámites registrales por jurisdicción** — **IGJ solo en CABA**; en **Santa Fe el registro es el
  RPJEC** (100% digital desde 2025, no es la IGJ). Sin extrapolar trámites entre jurisdicciones.

## Qué NO hace

- **No da asesoramiento contable, impositivo ni legal.** Toda salida es un **borrador para revisión de
  un contador matriculado**, que verifica los plazos y requisitos vigentes y asume la responsabilidad.
- **No afirma una fecha de vencimiento de ARCA** sin un recurso estático fechado o una RG recuperada.
  Sin fuente → `[verify]`.
- **No afirma que un régimen de información está vigente** ni su plazo sin recuperar la RG vigente.
- **No extrapola trámites de IGJ (CABA) a Santa Fe (RPJEC)**, ni viceversa. El RPJEC requiere login →
  trámites provinciales = **flujo asistido + `[verify]`**, confirmación manual.
- **No presenta una reforma/proyecto como vigente** sin verificar su entrada en vigor.
- **No presenta regímenes de información, DDJJ societarias ni inscripciones registrales**: esas acciones
  requieren confirmación del usuario y revisión profesional.

## Skills

| Skill | Invocación | Qué hace |
|---|---|---|
| `cold-start-interview` | `/societario-cumplimiento:cold-start-interview` | Entrevista de configuración del perfil. |
| `consulta-cumplimiento` | `/societario-cumplimiento:consulta-cumplimiento` | Responde una consulta de vencimientos / regímenes / trámites. |
| `buscar-normativa-societaria` | `/societario-cumplimiento:buscar-normativa-societaria` | Busca normativa/RG/calendario con los connectors. |
| `analizar-norma-societaria` | `/societario-cumplimiento:analizar-norma-societaria` | Recupera y resume una norma por id/número. |

## Connectors (MCP) — ver `.mcp.json`

Se ejecutan por stdio con `uv run --directory <connectors>`. Las rutas en `.mcp.json` son **absolutas a
la carpeta `connectors` de este repo en esta máquina** — ajustarlas si la instalación difiere (lección de
MCP-Juridico). El connector `arca` requiere `AFIP_WS_BASE_URL` configurado (afip-ws de NU, accesible por
Tailscale).

**Cobertura honesta:** el **RPJEC de Santa Fe requiere login → no hay connector**; los trámites registrales
provinciales son flujo asistido + `[verify]`. El **calendario de vencimientos de ARCA nacional** es recurso
estático/RG del Boletín (no hay API de calendario).

## Configuración persistida

El perfil personalizado se guarda en:
`~/.claude/plugins/config/mcp-contable/societario-cumplimiento/CLAUDE.md`

## Aviso

Herramienta de asistencia. **No reemplaza el criterio de un contador público matriculado.** Toda salida es
un borrador sujeto a revisión profesional. Autor: **Grupo NU**.
