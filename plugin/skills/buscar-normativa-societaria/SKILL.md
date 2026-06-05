---
name: buscar-normativa-societaria
description: >
  Busca normativa societaria y de cumplimiento argentina (Nación y Santa Fe) usando los connectors
  oficiales: ckan-juridico/ckan-nacional para datasets (hallar el id de InfoLEG de una norma, p. ej. la
  LGS 19.550), infoleg para recuperar una norma por id, boletin-nacional para RG de ARCA (calendario
  anual de vencimientos, regímenes de información), santafe-sin para normativa registral provincial,
  santafe-fiscal para el calendario impositivo SF. Siempre cita con source_url + retrieved_at + tier.
  Usar cuando el usuario pide encontrar/ubicar una norma, una RG, un vencimiento o un trámite registral.
user-invocable: true
---

# Buscar normativa societaria y de cumplimiento

## Propósito

Ubicar normas, resoluciones generales (RG de ARCA), datasets, calendarios o marcos registrales
relevantes para una consulta de cumplimiento, **con grounding**: cada resultado se cita con su fuente y
fecha de recuperación. No reemplaza el análisis (ver `analizar-norma-societaria`) ni autoriza afirmar
una fecha de vencimiento o la vigencia de un régimen sin verificarla.

## Connectors y tools disponibles

- **`arca`** (Tier A): `arca_get_constancia(cuit)` — constancia/padrón de un CUIT (razón social, estado,
  actividad; la **terminación del CUIT** define el grupo de vencimiento). `arca_health()`.
- **`ckan-juridico`** (Tier A — datos.jus.gob.ar):
  - `ckan_search_datasets(query)` / `ckan_list_datasets()` — descubrir datasets.
  - `ckan_get_dataset(slug)` — el dataset `base-de-datos-legislativos-infoleg` permite **hallar el id de
    InfoLEG** de una norma societaria (p. ej. LGS 19.550).
- **`ckan-nacional`** (Tier A — datos.gob.ar): datasets oficiales nacionales.
- **`infoleg`** (Tier B): `infoleg_get_norma(norma_id)` — recupera una norma nacional por **id numérico de
  InfoLEG** (LGS 19.550, etc.). `infoleg_search_norma(...)` da guía (no hace búsqueda programática).
- **`boletin-nacional`** (Tier B): `boletin_get_aviso(aviso_id, fecha, seccion)` — leer una **RG de ARCA**
  del Boletín por id + fecha: **calendario anual de vencimientos** y **regímenes de información**.
- **`santafe-sin`** (Tier B): búsqueda y detalle de normativa registral/fiscal de Santa Fe (incl. marco
  del **RPJEC** en la API provincial).
- **`santafe-fiscal`** (Tier B): `santafe_fiscal_list_calendarios()` /
  `santafe_fiscal_get_calendario(anio)` — URL oficial del **calendario impositivo SF** de un año (los
  vencimientos detallados se consultan en esa URL; no se inventan).

## Procedimiento

1. **Entender qué se busca:** ¿una **fecha de vencimiento** de ARCA?, ¿la vigencia de un **régimen de
   información**?, ¿la **LGS 19.550** u otra norma societaria?, ¿un **trámite registral** (IGJ/RPJEC)?
2. **Vencimientos ARCA:** el calendario anual sale de la **RG del año** (`boletin_nacional`, si tenés
   id+fecha) o del **recurso estático fechado** del proyecto. **Riesgo MUY ALTO:** no afirmes una fecha
   sin fuente fechada; si usás el recurso y pasó tiempo desde su fecha de corte → `[verify]`. Se puede
   indicar el **grupo por terminación de CUIT** (estructura), no la fecha sin fuente.
3. **Regímenes de información:** la vigencia y el plazo salen de la **RG vigente** (`boletin_nacional` /
   `infoleg`). No afirmes que un régimen (participaciones societarias, CITI) está vigente sin recuperarla.
4. **Norma societaria por tema/sin id (p. ej. LGS 19.550):** usá `ckan-juridico` (`ckan_get_dataset` sobre
   `base-de-datos-legislativos-infoleg`) para obtener el **id de InfoLEG**, y luego `infoleg_get_norma(id)`.
5. **Norma societaria con id:** llamá `infoleg_get_norma(id)` directo.
6. **Trámite registral Santa Fe (RPJEC):** usá `santafe_sin` para el marco normativo provincial. ⚠️ El
   **RPJEC requiere login → no hay connector** para el trámite en sí: describí el procedimiento general y
   marcá que se confirma manualmente contra el RPJEC (`[verify]`). **No uses normativa de IGJ para Santa Fe.**
7. **Trámite registral CABA (IGJ):** la **IGJ aplica solo a CABA**; su normativa se ubica en el Boletín /
   InfoLEG. No la apliques a entidades de otra jurisdicción.
8. **Citá cada hallazgo** con `source_url` + `retrieved_at` + tier.

## Grounding

- Mostrá para cada resultado: **`source_url`**, **`retrieved_at`** y **tier** del payload del connector.
- Tier A (ARCA/CKAN): cita autoritativa. Tier B (InfoLEG/Boletín/SIN/calendario SF): agregá
  `[scraped — verificar contra fuente oficial]`.
- **Sin resultado de connector (ni recurso fechado) → `[verify]`.** No completes de memoria un número de
  norma, una RG, una **fecha de vencimiento**, la **vigencia de un régimen** ni un requisito registral.
- Calendario ARCA y regímenes de información: aunque encuentres la norma marco, recordá que la **fecha y la
  vigencia** cambian seguido — confirmá el año / período vigente.

## Qué este skill NO hace

- **No** afirma una fecha de vencimiento ni la vigencia de un régimen sin un resultado de connector / recurso fechado.
- **No** inventa ids de InfoLEG, números de RG ni slugs: si no aparecen en un connector, lo dice.
- **No** hace búsqueda full-text confiable en InfoLEG (no hay API): el camino es vía id del dataset CKAN.
- **No** usa normativa de IGJ (CABA) para trámites de Santa Fe (RPJEC), ni viceversa.
- **No** analiza a fondo la norma — eso es `analizar-norma-societaria`.
- **No** es asesoramiento contable: los hallazgos son insumo para revisión del contador.
