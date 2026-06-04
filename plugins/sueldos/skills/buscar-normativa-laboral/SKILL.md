---
name: buscar-normativa-laboral
description: >
  Busca normativa laboral/previsional argentina (Nación y Santa Fe) usando los connectors oficiales:
  ckan-juridico/ckan-nacional para datasets (hallar el id de InfoLEG de una norma laboral), infoleg
  para recuperar una norma por id, boletin-nacional para RG de ARCA / Decretos / Resoluciones de
  seguridad social (alícuotas, topes, asignaciones), santafe-sin para normativa provincial,
  santafe-fiscal para el calendario impositivo SF. Siempre cita con source_url + retrieved_at + tier.
  Usar cuando el usuario pide encontrar/ubicar una norma, RG, tope o monto.
user-invocable: true
---

# Buscar normativa laboral

## Propósito

Ubicar normas, resoluciones generales (RG de ARCA), decretos, datasets o calendarios relevantes para
una consulta de nómina, **con grounding**: cada resultado se cita con su fuente y fecha de
recuperación. No reemplaza el análisis (ver `analizar-norma-laboral`) ni autoriza afirmar una cifra
sin verificarla.

## Connectors y tools disponibles

- **`arca`** (Tier A): `arca_get_constancia(cuit)` — constancia/padrón del CUIT del empleador.
  `arca_health()`.
- **`ckan-juridico`** (Tier A — datos.jus.gob.ar):
  - `ckan_search_datasets(query)` / `ckan_list_datasets()` — descubrir datasets.
  - `ckan_get_dataset(slug)` — el dataset `base-de-datos-legislativos-infoleg` permite **hallar el id
    de InfoLEG** de una norma laboral (LCT 20.744, SIPA 24.241, Asignaciones 24.714, ART 24.557, Ley
    Bases 27.742, etc.).
- **`ckan-nacional`** (Tier A — datos.gob.ar): datasets de empleo registrado, seguridad social.
- **`infoleg`** (Tier B): `infoleg_get_norma(norma_id)` — recupera una norma nacional por **id
  numérico de InfoLEG**. `infoleg_search_norma(...)` da guía (no hace búsqueda programática).
- **`boletin-nacional`** (Tier B): `boletin_get_aviso(aviso_id, fecha, seccion)` — leer una **RG de
  ARCA, Decreto o Resolución de seguridad social** (alícuotas de aportes/contribuciones, tope de la
  base imponible, montos de asignaciones familiares) por id + fecha.
- **`santafe-sin`** (Tier B): búsqueda y detalle de normativa fiscal/laboral provincial de Santa Fe.
- **`santafe-fiscal`** (Tier B): `santafe_fiscal_list_calendarios()` /
  `santafe_fiscal_get_calendario(anio)` — URL oficial del calendario impositivo SF de un año (los
  vencimientos detallados se consultan en esa URL; no se inventan).

## Procedimiento

1. **Entender qué se busca:** ¿una norma nacional concreta (LCT, SIPA, Asignaciones, ART)?, ¿una RG
   de ARCA / Decreto con alícuotas o topes?, ¿el monto de una asignación familiar?, ¿normativa
   provincial de Santa Fe?
2. **Norma nacional por tema/sin id:** usá `ckan-juridico` (`ckan_get_dataset` sobre
   `base-de-datos-legislativos-infoleg`) para obtener el **id de InfoLEG**, y luego
   `infoleg_get_norma(id)`.
3. **Norma nacional con id:** llamá `infoleg_get_norma(id)` directo.
4. **Alícuotas / topes / asignaciones por RG o Decreto:** si tenés id+fecha del Boletín,
   `boletin_get_aviso(...)`. **Riesgo MUY ALTO** para alícuotas de aportes/contribuciones, tope de la
   base imponible y montos de asignaciones: no afirmes el valor sin recuperar la norma vigente y
   confirmar el período.
5. **Normativa provincial Santa Fe:** usá `santafe_sin`.
6. **Vencimientos Santa Fe:** `santafe_fiscal_get_calendario(anio)` da la URL oficial; el vencimiento
   puntual se confirma ahí (no lo inventes).
7. **Citá cada hallazgo** con `source_url` + `retrieved_at` + tier.

## Grounding

- Mostrá para cada resultado: **`source_url`**, **`retrieved_at`** y **tier** del payload del connector.
- Tier A (ARCA/CKAN): cita autoritativa. Tier B (InfoLEG/Boletín/SIN/calendario SF): agregá
  `[scraped — verificar contra fuente oficial]`.
- **Sin resultado de connector → `[verify]`.** No completes de memoria un número de norma, una
  alícuota, un tope de base imponible, un monto de asignación, una escala de convenio ni una vigencia.
- Cargas sociales, topes, asignaciones y escalas de CCT: aunque encuentres la norma marco, recordá
  que los **valores concretos** se actualizan por movilidad/paritaria — confirmá el período vigente.

## Qué este skill NO hace

- **No** afirma alícuotas, topes, asignaciones, escalas ni montos sin un resultado de connector.
- **No** inventa ids de InfoLEG, números de RG/Decreto ni slugs: si no aparecen en un connector, lo dice.
- **No** hace búsqueda full-text confiable en InfoLEG (no hay API): el camino es vía id del dataset CKAN.
- **No** analiza a fondo la norma — eso es `analizar-norma-laboral`.
- **No** es asesoramiento contable: los hallazgos son insumo para revisión del contador.
