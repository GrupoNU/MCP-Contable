---
name: buscar-normativa-contable
description: >
  Busca normativa contable argentina usando los connectors oficiales para el marco LEGAL (CCyC Ley
  26.994, LGS Ley 19.550) y guía la verificación MANUAL de las Resoluciones Técnicas de la FACPCE
  (que no tienen connector). ckan-juridico/ckan-nacional para datasets (hallar el id de InfoLEG),
  infoleg para recuperar una norma por id, boletin-nacional para el Boletín, santafe-sin/fiscal para
  Santa Fe. Siempre cita con source_url + retrieved_at + tier; las RT se verifican contra
  facpce.org.ar y se marcan [verify]. Usar cuando el usuario pide encontrar/ubicar una norma o RT.
user-invocable: true
---

# Buscar normativa contable

## Propósito

Ubicar normas relevantes para una consulta de registración o estados contables, **con grounding**:
el **marco legal** (CCyC, LGS) se recupera por connector y se cita con su fuente y fecha; las **RT de
la FACPCE no tienen connector** y su cita se **verifica manualmente contra `facpce.org.ar`**. No
reemplaza el análisis (ver `analizar-norma-contable`) ni autoriza afirmar un número/objeto/vigencia
de una RT sin verificarlo.

## Connectors y tools disponibles

- **`arca`** (Tier A): `arca_get_constancia(cuit)` — constancia/padrón de un CUIT. `arca_health()`.
- **`ckan-juridico`** (Tier A — datos.jus.gob.ar):
  - `ckan_search_datasets(query)` / `ckan_list_datasets()` — descubrir datasets.
  - `ckan_get_dataset(slug)` — el dataset `base-de-datos-legislativos-infoleg` permite **hallar el id
    de InfoLEG** de una norma legal (CCyC Ley 26.994, LGS Ley 19.550).
- **`ckan-nacional`** (Tier A — datos.gob.ar): datasets oficiales nacionales.
- **`infoleg`** (Tier B): `infoleg_get_norma(norma_id)` — recupera una norma nacional por **id
  numérico de InfoLEG** (CCyC, LGS). `infoleg_search_norma(...)` da guía (no hace búsqueda programática).
- **`boletin-nacional`** (Tier B): `boletin_get_aviso(aviso_id, fecha, seccion)` — leer una norma del
  Boletín por id + fecha.
- **`santafe-sin`** (Tier B): normativa de Santa Fe (índice de la API provincial). Uso marginal aquí.
- **`santafe-fiscal`** (Tier B): calendario impositivo SF por año. Uso marginal (solo si una
  presentación contable se cruza con un vencimiento provincial).

> ⚠️ **Las RT de la FACPCE (6, 8, 9, 16, 17, 41/42, etc.) NO tienen connector.** No hay API de FACPCE;
> son un **recurso estático/futuro** (PDFs sueltos con fecha de corte). Su cita se **verifica
> manualmente contra `facpce.org.ar`** y, cuando corresponda, contra la resolución del **CPCE
> provincial** que la adopta. Hasta verificar → `[verify]`.

## Procedimiento

1. **Entender qué se busca:** ¿el **marco legal** de libros/estados (CCyC, LGS)?, ¿una **RT de la
   FACPCE**?, ¿un dataset oficial?
2. **Marco legal nacional por tema/sin id:** usá `ckan-juridico` (`ckan_get_dataset` sobre
   `base-de-datos-legislativos-infoleg`) para obtener el **id de InfoLEG** del CCyC (Ley 26.994) o la
   LGS (Ley 19.550), y luego `infoleg_get_norma(id)`.
3. **Marco legal con id:** llamá `infoleg_get_norma(id)` directo.
4. **RT de la FACPCE:** **no hay connector.** Indicá al usuario que la RT se **verifica manualmente
   contra `facpce.org.ar`** (número, objeto, texto vigente, modificatorias/derogación) y que, hasta
   confirmarlo, toda cita va con `[verify]`. Si se invocó la adopción provincial, recordá verificar
   la resolución del CPCE de la jurisdicción del ente.
5. **Coeficientes de ajuste por inflación (RT 6):** se publican periódicamente y se verifican (FACPCE
   / fuente del índice IPIM-IPC). **No los completes de memoria.**
6. **Citá cada hallazgo** con `source_url` + `retrieved_at` + tier (para lo recuperado por connector);
   para las RT, dejá explícito que la verificación es manual contra FACPCE.

## Grounding

- Para resultados de connector, mostrá: **`source_url`**, **`retrieved_at`** y **tier** del payload.
- Tier A (ARCA/CKAN): cita autoritativa. Tier B (InfoLEG/Boletín/SIN/calendario SF): agregá
  `[scraped — verificar contra fuente oficial]`.
- **Sin resultado de connector → `[verify]`.** No completes de memoria un número de ley, un id de
  InfoLEG ni una vigencia.
- **RT de la FACPCE: siempre `[verify]` hasta verificación manual contra `facpce.org.ar`.** No
  afirmes el número/objeto/vigencia de una RT ni un coeficiente de ajuste de memoria.

## Qué este skill NO hace

- **No** afirma número, objeto ni vigencia de una RT sin verificación manual contra FACPCE.
- **No** inventa ids de InfoLEG, números de ley ni slugs: si no aparecen en un connector, lo dice.
- **No** da coeficientes de ajuste por inflación de memoria.
- **No** hace búsqueda full-text confiable en InfoLEG (no hay API): el camino es vía id del dataset CKAN.
- **No** analiza a fondo la norma — eso es `analizar-norma-contable`.
- **No** es asesoramiento contable: los hallazgos son insumo para revisión del contador.
