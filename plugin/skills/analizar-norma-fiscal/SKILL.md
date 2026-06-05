---
name: analizar-norma-fiscal
description: >
  Dado el id de InfoLEG (o número/tipo/año) de una norma impositiva, la recupera con los connectors
  (infoleg_get_norma; ckan para hallar el id) y produce un resumen-análisis en borrador: objeto,
  artículos clave, vigencia conocida y puntos a verificar. Nunca transcribe alícuotas/montos que no
  estén en el texto recuperado. Usar cuando el usuario quiere entender o resumir una norma fiscal.
user-invocable: true
---

# Analizar norma fiscal

## Propósito

Recuperar una norma impositiva puntual y producir un **resumen/análisis en borrador** (objeto,
estructura, artículos relevantes, vigencia conocida, puntos a verificar). El análisis es **insumo**,
no asesoramiento ni liquidación.

## Procedimiento

1. **Identificar la norma:**
   - Si el usuario da un **id de InfoLEG**, andá al paso 2.
   - Si da número/tipo/año (p. ej. "Ley 23.349 de IVA") sin id, **derivá a `buscar-normativa-fiscal`**
     para obtener el id desde el dataset CKAN `base-de-datos-legislativos-infoleg`.
2. **Recuperar:** `infoleg_get_norma(norma_id)` (Tier B). Para una RG de ARCA, `boletin_get_aviso(...)`;
   para normativa fiscal de Santa Fe, `santafe_sin`.
3. **Analizar (borrador), estructurando:**
   - **Objeto/ámbito** de la norma (qué impuesto regula, sujetos, hecho imponible).
   - **Artículos clave** (citados con su número, **solo** si están en el texto recuperado).
   - **Vigencia:** lo que el connector confirma vía `retrieved_at`; si hay modificatorias o reformas
     posteriores no verificadas (p. ej. cambios 2024-2026 por Ley 27.743), marcarlo como punto a chequear.
   - **Puntos a verificar:** toda alícuota, tope, mínimo o categoría que el texto **no** contenga
     explícitamente, o que pueda haberse actualizado (monotributo, retenciones).
4. **Encabezado de work-product** según el rol del perfil (playbook §2).
5. **Gate:** cerrá recordando que el análisis es **borrador para revisión de un contador matriculado**.

## Aplicación del mapa de riesgo (playbook §4-§5)

- **IVA / Ganancias / IIBB:** marco conceptual citable; **no transcribas alícuotas** salvo que estén
  en el texto recuperado y aun así marcá que deben confirmarse como vigentes.
- **Monotributo (Ley 24.977):** MUY ALTO. Las **categorías/topes/cuotas se actualizan por IPC**: no
  los afirmes de memoria; si no están en el texto recuperado y reciente, `[verify]`.
- **Retenciones/percepciones (RG ARCA):** MUY ALTO. No afirmes alícuotas sin recuperar la RG vigente.
- **Ley 27.743 / reformas 2024-2026:** distinguí qué artículos están **vigentes** y desde cuándo; no
  presentes un proyecto/anuncio como vigente.

## Grounding

- Toda afirmación sobre el contenido de la norma debe apoyarse en el **texto recuperado** por el
  connector, citando `source_url` + `retrieved_at` + tier.
- Tier B (InfoLEG/Boletín/SIN): agregá `[scraped — verificar contra fuente oficial]`.
- **Sin recuperación exitosa → no analices de memoria:** decí que no pudiste recuperar la norma y todo
  lo que digas del tema va con `[verify]`.

## Qué este skill NO hace

- **No** analiza de memoria: sin texto recuperado, no produce análisis afirmativo.
- **No** transcribe alícuotas, topes ni categorías que no estén en el texto recuperado.
- **No** confirma vigencia de reformas/modificatorias no recuperadas.
- **No** trata un proyecto/anuncio (p. ej. una reforma "que se viene") como norma vigente.
- **No** es asesoramiento contable: el análisis es un borrador para el contador.
