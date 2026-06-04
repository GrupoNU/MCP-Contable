# Grounding anti-alucinación — MCP-Contable

> El principio innegociable. En contable es **aún más crítico que en legal**: hay montos,
> alícuotas, topes, vencimientos y categorías que cambian constantemente (mensual/semestral).
> Última actualización: 2026-06-04.

## Principio

**Toda salida es un borrador para revisión de un contador matriculado.** El sistema nunca
afirma un monto/alícuota/categoría/vencimiento sin trazabilidad a una fuente, con fecha de
recuperación.

## Sistema de tiers de fuente

Implementado en `connectors/src/mcp_contable/common/grounding.py`. Toda tool de un connector
envuelve su resultado con `ground(data, tier, source_url)` y lo serializa con `to_dict()`:

```json
{
  "data": "...",
  "source_tier": "A | B | C",
  "source_url": "https://...",
  "retrieved_at": "2026-06-04T12:00:00+00:00",
  "notes": "",
  "citation_flag": "..."
}
```

| Tier | Qué es | `citation_flag` | Cómo lo usa Claude |
|---|---|---|---|
| **A** | API oficial estructurada (ARCA vía afip-ws, CKAN datos.gob.ar / datos.jus.gob.ar) | `""` (sin marca) | Cita usable, autoritativa |
| **B** | Scraping de fuente oficial predecible (InfoLEG, Boletín, SIN SF, calendario SF) | `[scraped — verificar contra fuente oficial]` | Usable, pero advierte verificar |
| **C** | Sin connector / conocimiento del modelo | `[verify]` | Marca obligatoria de no-verificado |

## Reglas para los plugins (en sus CLAUDE.md de producto)

1. **Sin tool result de Tier A/B en contexto, TODA cifra/cita lleva `[verify]`.** Sin excepción "lo sé de memoria".
2. **Nunca** afirmar un monto, alícuota, tope, mínimo, categoría de monotributo, fecha de
   vencimiento o coeficiente sin un `retrieved_at` reciente de un connector. Sin fuente → marco
   conceptual + `[verify]`, nunca el número.
3. Mostrar siempre `source_url` + `retrieved_at` + tier al citar.
4. Distinguir visualmente lo verificado (Tier A) de lo que requiere chequeo (Tier B/C).
5. Los **recursos estáticos** en `recursos/` (tabla de monotributo, calendario ARCA, RT FACPCE)
   son Tier A pero con **fecha de corte explícita**: si pasó tiempo desde la captura, `[verify]`.
6. **Distinguir PROYECTO de NORMA VIGENTE.** Una reforma anunciada o un proyecto de ley no es
   derecho vigente hasta su sanción/publicación.

## Gate de consecuencias

Presentar una DDJJ, generar un F.931, registrar un asiento que cierra un período → requiere
**confirmación explícita** + recordatorio de revisión por un profesional matriculado.

## Por qué importa en lo contable argentino

- ARCA (ex-AFIP desde Dec. 953/2024) actualiza topes de monotributo por IPC, alícuotas,
  mínimos no imponibles y calendarios de vencimientos con frecuencia. Una cifra sin fecha es peligrosa.
- El riesgo nº1 es **un monto/alícuota desactualizado presentado como vigente.** Tratá todo
  número como "verificar contra fuente" por defecto.

## Verificación

Tests del sistema de tiers: `connectors/tests/test_grounding.py` (Fase 0, verde — 36 tests con
http y cache). Cada connector futuro debe testear que sus tools devuelven `source_tier` +
`retrieved_at` poblados.
