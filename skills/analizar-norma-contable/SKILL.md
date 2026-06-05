---
name: analizar-norma-contable
description: >
  Dado el id de InfoLEG (o número/tipo/año) de una norma legal contable (CCyC Ley 26.994, LGS Ley
  19.550), la recupera con los connectors (infoleg_get_norma; ckan para hallar el id) y produce un
  resumen-análisis en borrador. Para una RT de la FACPCE (sin connector), estructura el análisis y
  marca lo que debe verificarse manualmente contra facpce.org.ar. Nunca transcribe criterios de una
  RT ni coeficientes que no estén en un texto recuperado/verificado. Usar cuando el usuario quiere
  entender o resumir una norma contable.
user-invocable: true
---

# Analizar norma contable

## Propósito

Recuperar una norma contable puntual y producir un **resumen/análisis en borrador** (objeto,
estructura, artículos relevantes, vigencia conocida, puntos a verificar). Para el **marco legal**
(CCyC, LGS) el texto se recupera por connector; para una **RT de la FACPCE** (sin connector) se
estructura el análisis y se marca lo que debe **verificarse manualmente contra `facpce.org.ar`**. El
análisis es **insumo**, no asesoramiento ni registración.

## Procedimiento

1. **Identificar la norma:**
   - **Marco legal con id de InfoLEG** → andá al paso 2.
   - **Marco legal con número/tipo/año** (p. ej. "CCyC Ley 26.994", "LGS Ley 19.550") sin id →
     **derivá a `buscar-normativa-contable`** para obtener el id desde el dataset CKAN
     `base-de-datos-legislativos-infoleg`.
   - **RT de la FACPCE** (6, 8, 9, 16, 17, 41/42, etc.) → **no hay connector**: andá al paso 3.
2. **Recuperar el marco legal:** `infoleg_get_norma(norma_id)` (Tier B). Para una norma del Boletín,
   `boletin_get_aviso(...)`.
3. **RT de la FACPCE (sin connector):** estructurá el análisis sobre el **marco conceptual estable**
   (p. ej. qué es la reexpresión, qué es un rubro, qué es la presentación de estados contables) y
   marcá **explícitamente** que el **número, el objeto, el texto vigente y la vigencia de la RT se
   verifican manualmente contra `facpce.org.ar`** (y la adopción del CPCE provincial cuando
   corresponda). No transcribas el articulado de la RT de memoria.
4. **Analizar (borrador), estructurando:**
   - **Objeto/ámbito** de la norma (qué regula, sujetos/entes alcanzados).
   - **Artículos clave** (citados con su número, **solo** si están en el texto recuperado del CCyC/LGS;
     para una RT, solo si hay fuente verificada en contexto).
   - **Vigencia:** lo que el connector confirma vía `retrieved_at` (marco legal); para una RT, marcar
     que la vigencia/modificatorias/derogación se confirman contra FACPCE.
   - **Puntos a verificar:** todo criterio de medición/exposición, coeficiente de ajuste, índice o
     umbral de ente pequeño/mediano que **no** esté en un texto recuperado/verificado.
5. **Encabezado de work-product** según el rol del perfil (playbook §2).
6. **Gate:** cerrá recordando que el análisis es **borrador para revisión de un contador matriculado**.

## Aplicación del mapa normativo (playbook §3-§5)

- **Marco conceptual (partida doble, asientos, rubros, qué son los estados contables):** estable, se
  explica sin cita de RT.
- **RT 16 / RT 8 / RT 9 (marco conceptual, presentación, rubros):** el concepto se explica; el
  **número/objeto/vigencia** se verifica contra FACPCE → `[verify]`.
- **RT 17 (medición):** ALTO. No afirmes criterios de medición concretos como verdad fija de memoria;
  se citan contra el texto vigente verificado.
- **RT 6 (ajuste por inflación):** MUY ALTO. El **coeficiente/índice (IPIM/IPC)** se verifica; nunca
  de memoria. La activación/vigencia del ajuste también se confirma.
- **RT 41 / RT 42 (entes pequeños/medianos):** los **umbrales** se actualizan; no los afirmes de
  memoria, confirmá encuadre y vigencia contra FACPCE.
- **Proyecto vs. vigente:** una RT en consulta/borrador NO es norma vigente; confirmá aprobación de la
  FACPCE y adopción provincial.

## Grounding

- Toda afirmación sobre el contenido de una norma del **marco legal** debe apoyarse en el **texto
  recuperado** por el connector, citando `source_url` + `retrieved_at` + tier. Tier B
  (InfoLEG/Boletín): agregá `[scraped — verificar contra fuente oficial]`.
- **RT de la FACPCE:** sin texto verificado en contexto, **no transcribas su articulado ni afirmes su
  vigencia**; marcá `[verify]` y derivá a la verificación manual contra `facpce.org.ar`.
- **Sin recuperación/verificación exitosa → no analices de memoria:** decí que no pudiste recuperarla
  y todo lo que digas del tema va con `[verify]`.

## Qué este skill NO hace

- **No** analiza de memoria: sin texto recuperado/verificado, no produce análisis afirmativo del
  articulado.
- **No** transcribe criterios de una RT, coeficientes de ajuste ni umbrales que no estén en fuente
  verificada.
- **No** confirma la vigencia de una RT ni de sus modificatorias sin verificación contra FACPCE.
- **No** trata un proyecto/borrador de RT como norma vigente.
- **No** es asesoramiento contable: el análisis es un borrador para el contador.
