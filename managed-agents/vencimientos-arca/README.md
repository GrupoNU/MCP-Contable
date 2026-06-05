# vencimientos-arca — managed-agent cookbook

Monitor de **vencimientos impositivos y de seguridad social ante ARCA** (ex-AFIP) para el
contribuyente del estudio: DDJJ y pago de IVA, F.931, Ganancias, Bienes Personales, monotributo y
retenciones/percepciones, por terminación de CUIT. Alerta los que están próximos a vencer.

Plugin de área asociado: **`societario-cumplimiento`** (vencimientos / cumplimiento).

## ⚠️ Qué es y qué NO es

- Es un **cookbook, no un producto.** Es una plantilla declarativa de Claude Managed Agents (Claude
  API). **NO corre hoy en Cowork** (que ejecuta los plugins de Claude Code interactivamente). Deja
  lista la capa de automatización para un futuro modo desatendido.
- **NO es un reemplazo del contador.** Monitorea y redacta borradores de alerta. Un contador
  matriculado verifica cada fecha contra ARCA y decide. Toda salida es un **lead / borrador**.

## El riesgo nº1 que este agente está diseñado para NO cometer

En vencimientos fiscales el peligro no es solo perder una fecha: es **afirmar una fecha
DESACTUALIZADA como vigente**. El calendario de ARCA cambia por RG cada año. Por eso el agente:

- **Nunca afirma una fecha** que no venga de un **recurso fechado vigente**
  (`recursos/calendario-vencimientos-arca.md` con fecha de corte del año en curso) o de una **RG de
  ARCA recuperada** por connector.
- Si no hay calendario fechado vigente, lo dice y marca todo como **`[verify]`** — no inventa fechas.
- Marca cada alerta con `requiere_verificacion` cuando corresponde, y cierra con un **pie de
  verificación obligatorio**.

## Arquitectura de seguridad de 3 niveles

El contenido leído (config del contribuyente, calendario, RG) es **input NO confiable**. Toda
instrucción dentro de un documento es **data, no un comando**.

1. **`vencimiento-reader`** (reader) — lee el calendario fechado + la config + (opcional) una RG por
   connector. SOLO `read`/`grep` + connectors de lectura (`boletin-nacional`, `santafe-fiscal`). **No
   tiene Write.** Devuelve JSON validado por schema. Si el calendario está sin completar/vencido,
   devuelve `calendario_fechado: false` y no inventa fechas.
2. **`vencimiento-calculator`** (analyzer) — computación pura: días restantes y urgencia sobre el
   JSON del reader. **No tiene Write, ni web, ni MCP.** Marca `requiere_verificacion` / `sin_fuente`.
3. **`alerta-writer`** (writer) — **único con Write.** Produce el reporte en `./out/`. Nunca ve el
   documento crudo; formatea lo validado, con defensa contra injection y el pie de verificación.

El **orquestador** (`agent.yaml`) NO tiene Write y NO lee documentos crudos: solo enruta.

## Connectors usados (Tier A/B)

Los del `.mcp.json` del plugin `societario-cumplimiento`, ejecutados por stdio con `uv run` sobre
`../../connectors`:
- `boletin-nacional` (Tier B) — recuperar una RG de ARCA del Boletín.
- `santafe-fiscal` (Tier B) — calendario de Ingresos Brutos de Santa Fe (provincial).

## Lo que obtenés y lo que no

- **Obtenés:** una estructura de manifest funcional con tiers de seguridad, el grounding
  anti-desactualización cableado, y ejemplos de steering.
- **No obtenés:** un agente production-ready (hay que cablear la config del contribuyente, fijar la
  cadencia, completar el recurso de calendario con su fecha, configurar el ruteo de notificaciones y
  correr tu propia evaluación), ni un reemplazo del contador.
