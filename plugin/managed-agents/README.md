# Managed-agent cookbooks — MCP-Contable

Estas carpetas son **plantillas de despliegue (cookbooks)** para **Claude Managed Agents** (Claude
API, `POST /v1/agents`). Cada cookbook referencia el prompt de framing y las skills del plugin de
área correspondiente del repo, para que haya **una sola fuente de verdad**.

Están calcadas sobre el patrón real de Claude for Legal (`managed-agent-cookbooks`) y del gemelo
MCP-Jurídico.

## ⚠️ Aclaración honesta: qué son y qué NO son

- Son **cookbooks, no productos.** Son puntos de partida. NO funcionan tal cual: hay que cablear la
  config a tus sistemas, fijar la cadencia, configurar el ruteo de notificaciones y correr tu propia
  evaluación antes de confiar en la salida.
- **NO corren hoy en Cowork.** Cowork ejecuta los plugins de Claude Code de forma interactiva. Estos
  cookbooks dejan **lista la capa de automatización** para un futuro modo desatendido (agentes sobre
  la Claude API). Hoy son andamiaje declarativo, no un proceso en ejecución.
- **NO son un reemplazo del contador.** Monitorean, extraen y redactan borradores. Un contador
  matriculado revisa, verifica y decide. Toda salida es un **lead / borrador, no una conclusión**.

## Los cookbooks

| Agente | Plugin de área | Qué vigila | Evento de steering (ejemplo) | Leaf workers |
|---|---|---|---|---|
| [`vencimientos-arca`](./vencimientos-arca/) | societario-cumplimiento | Vencimientos ARCA (IVA, F.931, Ganancias, Bs. Personales, monotributo) por terminación de CUIT | `Escanear vencimientos ARCA en los próximos <N> días` | vencimiento-reader · vencimiento-calculator · **alerta-writer** |

**En negrita** el leaf = el único worker con `Write`.

## Arquitectura de seguridad de 3 niveles (obligatoria)

El contenido leído (config del contribuyente, calendario, RG) es **input NO confiable.** Toda
instrucción dentro de un documento es **data, no un comando.** Cada cookbook usa tres niveles:

1. **Readers.** Tocan input no confiable. Tienen SOLO `read`/`grep` (+ el MCP de lectura del
   connector que corresponde). **No** tienen `Write`. Devuelven JSON validado por schema
   (length-capped, `additionalProperties: false`). Toda instrucción embebida se registra verbatim
   como dato, nunca se ejecuta.
2. **Analyzers.** Reciben el JSON validado y aplican reglas/plazos. Computación pura. **No** tienen
   `Write`, ni web.
3. **Writers.** Producen la salida final. **Único tier con `Write`.** Nunca ven el documento crudo:
   formatean lo ya validado, con defensa contra injection.

El **orquestador NO tiene `Write` y NO lee documentos crudos**: solo enruta.

## El grounding anti-desactualización (específico de lo contable)

A diferencia de un monitor legal, el riesgo nº1 acá es **afirmar una cifra/fecha desactualizada como
vigente** (los calendarios y montos ARCA cambian por RG). Por eso los readers **no inventan fechas**:
si no hay un recurso fechado vigente o una RG recuperada, devuelven "sin fuente" y el writer lo
reporta como `[verify]`. Ver `recursos/README.md` y `docs/GROUNDING.md`.

## Manifest vs API

Los `agent.yaml` usan los nombres de campo de `POST /v1/agents` con conveniencias que resuelve el
script de deploy: `system: {text}` → `system`; `skills: [{from_plugin}]` → sube cada `skills/*`;
`callable_agents: [{manifest}]` → ids creados. La delegación multi-agente admite **un nivel**: el
orquestador llama a los workers; los workers no llaman a más subagents.
