---
name: analizar-norma-societaria
description: >
  Dado el id de InfoLEG (o número/tipo/año) de una norma societaria o de cumplimiento, la recupera con
  los connectors (infoleg_get_norma; ckan para hallar el id; boletin_get_aviso para una RG de ARCA) y
  produce un resumen-análisis en borrador: objeto, artículos clave, vigencia conocida y puntos a
  verificar. Nunca transcribe fechas de vencimiento ni plazos que no estén en el texto recuperado. Usar
  cuando el usuario quiere entender o resumir una norma societaria, una RG o un régimen de información.
user-invocable: true
---

# Analizar norma societaria

## Propósito

Recuperar una norma societaria o de cumplimiento puntual y producir un **resumen/análisis en borrador**
(objeto, estructura, artículos relevantes, vigencia conocida, puntos a verificar). El análisis es
**insumo**, no asesoramiento ni presentación.

## Procedimiento

1. **Identificar la norma:**
   - Si el usuario da un **id de InfoLEG**, andá al paso 2.
   - Si da número/tipo/año (p. ej. "Ley 19.550 General de Sociedades") sin id, **derivá a
     `buscar-normativa-societaria`** para obtener el id desde el dataset CKAN
     `base-de-datos-legislativos-infoleg`.
   - Si es una **RG de ARCA** (calendario de vencimientos, régimen de información), necesitás id+fecha del
     Boletín.
2. **Recuperar:** `infoleg_get_norma(norma_id)` (Tier B) para una ley. Para una **RG de ARCA**,
   `boletin_get_aviso(...)` (Tier B). Para normativa registral de Santa Fe, `santafe_sin` (Tier B).
3. **Analizar (borrador), estructurando:**
   - **Objeto/ámbito** de la norma (qué regula: tipos societarios y órganos en la LGS; sujetos obligados y
     periodicidad en un régimen de información; grupos por terminación de CUIT en un calendario).
   - **Artículos clave** (citados con su número, **solo** si están en el texto recuperado).
   - **Vigencia:** lo que el connector confirma vía `retrieved_at`; si hay modificatorias o reformas
     posteriores no verificadas (p. ej. la incorporación de la SAS por Ley 27.349, o un cambio de
     calendario/RG posterior), marcarlo como punto a chequear.
   - **Puntos a verificar:** toda **fecha de vencimiento, plazo, vigencia de régimen o requisito registral**
     que el texto **no** contenga explícitamente, o que pueda haberse actualizado (calendario anual,
     regímenes de información).
4. **Encabezado de work-product** según el rol del perfil (playbook §2).
5. **Gate:** cerrá recordando que el análisis es **borrador para revisión de un contador matriculado**.

## Aplicación del mapa de riesgo (playbook §4-§5)

- **Calendario de vencimientos ARCA:** MUY ALTO. Las **fechas cambian cada año por RG**: no las afirmes de
  memoria; si no están en el texto/RG recuperado y reciente, `[verify]`. Se puede describir la **estructura
  por terminación de CUIT**, no la fecha sin fuente fechada.
- **Regímenes de información (RG ARCA):** MUY ALTO. No afirmes que un régimen está **vigente** ni su
  **plazo** sin recuperar la RG vigente. Distinguí el régimen del año/período correcto.
- **LGS 19.550:** marco conceptual citable (tipos societarios, órganos, obligaciones de los administradores,
  balance y memoria) **solo** sobre el texto recuperado; marcá que las modificatorias/reformas se confirman.
- **Trámites registrales (IGJ/RPJEC):** **IGJ = solo CABA; RPJEC = Santa Fe.** No describas un trámite de una
  jurisdicción como si aplicara en la otra. El RPJEC requiere login → flujo asistido + `[verify]`.
- **Reformas 2024-2026:** distinguí qué está **vigente** y desde cuándo; no presentes un proyecto/anuncio como vigente.

## Grounding

- Toda afirmación sobre el contenido de la norma debe apoyarse en el **texto recuperado** por el connector,
  citando `source_url` + `retrieved_at` + tier.
- Tier B (InfoLEG/Boletín/SIN): agregá `[scraped — verificar contra fuente oficial]`.
- **Sin recuperación exitosa → no analices de memoria:** decí que no pudiste recuperar la norma y todo lo
  que digas del tema va con `[verify]`.

## Qué este skill NO hace

- **No** analiza de memoria: sin texto recuperado, no produce análisis afirmativo.
- **No** transcribe fechas de vencimiento, plazos ni la vigencia de un régimen que no estén en el texto recuperado.
- **No** confirma vigencia de reformas/modificatorias no recuperadas.
- **No** extrapola trámites de IGJ (CABA) a Santa Fe (RPJEC), ni viceversa.
- **No** trata un proyecto/anuncio (p. ej. una reforma de la LGS "que se viene") como norma vigente.
- **No** es asesoramiento contable ni legal: el análisis es un borrador para el contador.
