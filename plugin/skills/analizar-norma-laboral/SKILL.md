---
name: analizar-norma-laboral
description: >
  Dado el id de InfoLEG (o número/tipo/año) de una norma laboral/previsional, la recupera con los
  connectors (infoleg_get_norma; ckan para hallar el id; boletin para RG/Decretos) y produce un
  resumen-análisis en borrador: objeto, artículos clave, vigencia conocida y puntos a verificar.
  Nunca transcribe alícuotas/topes/asignaciones/escalas que no estén en el texto recuperado. Usar
  cuando el usuario quiere entender o resumir una norma laboral.
user-invocable: true
---

# Analizar norma laboral

## Propósito

Recuperar una norma laboral/previsional puntual y producir un **resumen/análisis en borrador**
(objeto, estructura, artículos relevantes, vigencia conocida, puntos a verificar). El análisis es
**insumo**, no asesoramiento ni liquidación.

## Procedimiento

1. **Identificar la norma:**
   - Si el usuario da un **id de InfoLEG**, andá al paso 2.
   - Si da número/tipo/año (p. ej. "Ley 20.744 de Contrato de Trabajo") sin id, **derivá a
     `buscar-normativa-laboral`** para obtener el id desde el dataset CKAN
     `base-de-datos-legislativos-infoleg`.
2. **Recuperar:** `infoleg_get_norma(norma_id)` (Tier B). Para una RG de ARCA / Decreto / Resolución
   de seguridad social, `boletin_get_aviso(...)`; para normativa provincial de Santa Fe, `santafe_sin`.
3. **Analizar (borrador), estructurando:**
   - **Objeto/ámbito** de la norma (qué regula: relación laboral, sistema previsional, asignaciones,
     riesgos del trabajo; sujetos alcanzados).
   - **Artículos clave** (citados con su número, **solo** si están en el texto recuperado).
   - **Vigencia:** lo que el connector confirma vía `retrieved_at`; si hay modificatorias o reformas
     posteriores no verificadas (p. ej. cambios por Ley 27.742 / Ley Bases), marcarlo como punto a chequear.
   - **Puntos a verificar:** toda alícuota, tope de base imponible, mínimo, monto de asignación o
     escala de convenio que el texto **no** contenga explícitamente, o que pueda haberse actualizado
     por movilidad/paritaria.
4. **Encabezado de work-product** según el rol del perfil (playbook §2).
5. **Gate:** cerrá recordando que el análisis es **borrador para revisión de un contador matriculado**.

## Aplicación del mapa de riesgo (playbook §4-§5)

- **LCT (Ley 20.744):** marco conceptual citable; **no transcribas topes indemnizatorios ni montos**
  salvo que estén en el texto recuperado, y aun así marcá que deben confirmarse como vigentes.
- **Cargas sociales / SIPA (Ley 24.241) y topes de base imponible:** MUY ALTO. Las **alícuotas y el
  tope/mínimo de la base se actualizan** (Dec./RG ARCA, movilidad): no los afirmes de memoria; si no
  están en el texto recuperado y reciente, `[verify]`.
- **Asignaciones familiares (Ley 24.714):** MUY ALTO. **Montos y rangos de IGF se actualizan por
  movilidad**: no afirmarlos sin recuperar la resolución vigente.
- **Convenios colectivos (CCT):** MUY ALTO. No afirmes básicos ni categorías sin la escala vigente
  del acuerdo paritario.
- **ART (Ley 24.557):** la **alícuota la fija la aseguradora** — no surge de la ley; no la afirmes.
- **Ley 27.742 / reforma laboral 2024-2026:** distinguí qué artículos están **vigentes** y desde
  cuándo; no presentes un proyecto/anuncio como vigente. **No confundir con la reforma fiscal (Ley 27.743).**

## Grounding

- Toda afirmación sobre el contenido de la norma debe apoyarse en el **texto recuperado** por el
  connector, citando `source_url` + `retrieved_at` + tier.
- Tier B (InfoLEG/Boletín/SIN): agregá `[scraped — verificar contra fuente oficial]`.
- **Sin recuperación exitosa → no analices de memoria:** decí que no pudiste recuperar la norma y todo
  lo que digas del tema va con `[verify]`.

## Qué este skill NO hace

- **No** analiza de memoria: sin texto recuperado, no produce análisis afirmativo.
- **No** transcribe alícuotas, topes, asignaciones ni escalas que no estén en el texto recuperado.
- **No** confirma vigencia de reformas/modificatorias no recuperadas.
- **No** trata un proyecto/anuncio (p. ej. una reforma laboral "que se viene") como norma vigente.
- **No** es asesoramiento contable: el análisis es un borrador para el contador.
