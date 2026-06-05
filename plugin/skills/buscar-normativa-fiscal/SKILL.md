---
name: buscar-normativa-fiscal
description: >
  Busca normativa impositiva argentina (Nación y Santa Fe) usando los connectors oficiales:
  ckan-juridico/ckan-nacional para datasets (hallar el id de InfoLEG de una norma fiscal), infoleg
  para recuperar una norma por id, boletin-nacional para RG de ARCA, santafe-sin para normativa
  fiscal provincial, santafe-fiscal para el calendario impositivo SF. Siempre cita con source_url +
  retrieved_at + tier. Usar cuando el usuario pide encontrar/ubicar una norma, RG o vencimiento.
user-invocable: true
---

# Buscar normativa fiscal

## Propósito

Ubicar normas, resoluciones generales (RG de ARCA), datasets o calendarios relevantes para una
consulta impositiva, **con grounding**: cada resultado se cita con su fuente y fecha de recuperación.
No reemplaza el análisis (ver `analizar-norma-fiscal`) ni autoriza afirmar una cifra sin verificarla.

## Connectors y tools disponibles

- **`arca`** (Tier A): `arca_get_constancia(cuit)` — constancia/padrón de un CUIT. `arca_health()`.
- **`ckan-juridico`** (Tier A — datos.jus.gob.ar):
  - `ckan_search_datasets(query)` / `ckan_list_datasets()` — descubrir datasets.
  - `ckan_get_dataset(slug)` — el dataset `base-de-datos-legislativos-infoleg` permite **hallar el id
    de InfoLEG** de una norma fiscal (IVA 23.349, Ganancias 20.628, Monotributo 24.977, etc.).
- **`ckan-nacional`** (Tier A — datos.gob.ar): datasets de recaudación tributaria, MiPyME.
- **`infoleg`** (Tier B): `infoleg_get_norma(norma_id)` — recupera una norma nacional por **id
  numérico de InfoLEG**. `infoleg_search_norma(...)` da guía (no hace búsqueda programática).
- **`boletin-nacional`** (Tier B): `boletin_get_aviso(aviso_id, fecha, seccion)` — leer una **RG de
  ARCA** u otra norma publicada en el Boletín por id + fecha.
- **`santafe-sin`** (Tier B): búsqueda y detalle de normativa fiscal de Santa Fe (Código Fiscal Ley
  3456, RG de la API provincial).
- **`santafe-fiscal`** (Tier B): `santafe_fiscal_list_calendarios()` /
  `santafe_fiscal_get_calendario(anio)` — URL oficial del **calendario impositivo SF** de un año
  (los vencimientos detallados se consultan en esa URL; no se inventan).

## Procedimiento

1. **Entender qué se busca:** ¿una norma nacional concreta (IVA/Ganancias/Monotributo)?, ¿una RG de
   ARCA?, ¿normativa fiscal de Santa Fe?, ¿un vencimiento?
2. **Norma nacional por tema/sin id:** usá `ckan-juridico` (`ckan_get_dataset` sobre
   `base-de-datos-legislativos-infoleg`) para obtener el **id de InfoLEG**, y luego
   `infoleg_get_norma(id)`.
3. **Norma nacional con id:** llamá `infoleg_get_norma(id)` directo.
4. **RG de ARCA:** si tenés id+fecha del Boletín, `boletin_get_aviso(...)`. **Riesgo MUY ALTO** para
   alícuotas de retención/percepción: no afirmes la alícuota sin recuperar la RG vigente.
5. **Normativa fiscal Santa Fe:** usá `santafe_sin` (Código Fiscal, RG de la API). Recordá Convenio
   Multilateral si la entidad tributa en más de una jurisdicción.
6. **Vencimientos Santa Fe:** `santafe_fiscal_get_calendario(anio)` da la URL oficial; el vencimiento
   puntual se confirma ahí (no lo inventes).
7. **Citá cada hallazgo** con `source_url` + `retrieved_at` + tier.

## Grounding

- Mostrá para cada resultado: **`source_url`**, **`retrieved_at`** y **tier** del payload del connector.
- Tier A (ARCA/CKAN): cita autoritativa. Tier B (InfoLEG/Boletín/SIN/calendario SF): agregá
  `[scraped — verificar contra fuente oficial]`.
- **Sin resultado de connector → `[verify]`.** No completes de memoria un número de norma, una
  alícuota, un tope de monotributo, un vencimiento ni una vigencia.
- Monotributo y retenciones/percepciones: aunque encuentres la norma marco, recordá que los
  **valores concretos** se actualizan seguido — confirmá el período vigente.

## Qué este skill NO hace

- **No** afirma alícuotas, topes ni vencimientos sin un resultado de connector.
- **No** inventa ids de InfoLEG, números de RG ni slugs: si no aparecen en un connector, lo dice.
- **No** hace búsqueda full-text confiable en InfoLEG (no hay API): el camino es vía id del dataset CKAN.
- **No** analiza a fondo la norma — eso es `analizar-norma-fiscal`.
- **No** es asesoramiento contable: los hallazgos son insumo para revisión del contador.
