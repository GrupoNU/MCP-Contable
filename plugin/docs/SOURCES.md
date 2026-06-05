# Catálogo de fuentes — MCP-Contable

> Fuentes fiscales/contables argentinas y su acceso técnico verificado. Tier según `GROUNDING.md`.
> Última actualización: 2026-06-04. ✅ = acceso verificado de primera mano (curl/WebFetch).

## Nación (ARCA + datos abiertos)

| Fuente | Tier | Acceso | Estado | Connector |
|---|---|---|---|---|
| **ARCA Constancia/Padrón** (vía afip-ws de NU) | A | HTTP al microservicio afip-ws (`GET /fiscal/cuit/{cuit}`) | ✅ **OPERATIVO** (2026-06-04): afip-ws expuesto a Tailscale; padrón real de NU devuelto; live test verde | `arca` |
| **datos.gob.ar** (CKAN nacional) | A | API REST `/api/3/action/*` (JSON) | ✅ `package_search` → success:true | `ckan_nacional` |
| **datos.jus.gob.ar** (CKAN) | A | API REST (JSON) | ✅ (heredado de Legal); dataset `base-de-datos-legislativos-infoleg` confirmado | `ckan_juridico` |
| **InfoLEG** (Ley IVA 23.349, Ganancias 20.628, Monotributo 24.977, Proc. Trib. 11.683) | B | URL predecible `verNorma.do?id=X` + descarga ZIP vía CKAN | ✅ patrón confirmado (recuperar por id) | `infoleg` |
| **Boletín Oficial Nac.** (RG ARCA) | B | Scraping (sin API oficial) | existe, scrapeable | `boletin_nacional` |
| **ARCA web services directos** (sin afip-ws) | — | WSAA + certificado | requiere cert. → se usa vía afip-ws, no directo | (vía `arca`) |
| **Monotributo** (categorías/topes/cuotas) | C → estático | No en datos abiertos; solo HTML ARCA | recurso estático con fecha de corte + `[verify]` | `recursos/` |
| **Calendario de vencimientos ARCA** | C/B → estático | Sin recurso estructurado público confirmado | recurso estático con fecha de corte; lo consume el managed-agent | `recursos/` |

### Datasets CKAN útiles confirmados
- `datos.jus.gob.ar`: `base-de-datos-legislativos-infoleg` (→ ids de normas fiscales nacionales).
- `datos.gob.ar`: datasets de recaudación tributaria (SSPM), registro MiPyME, seguridad social.

## Santa Fe (provincial — IIBB)

| Fuente | Tier | Acceso | Estado | Connector |
|---|---|---|---|---|
| **SIN** (Sist. Info Normativa) | B | Scraping santafe.gob.ar/normativa | ✅ (heredado de Legal); Código Fiscal Ley 3456, RG de API | `santafe_sin` |
| **Calendario impositivo SF** | B | HTML (`/content/view/full/111353`) | ✅ HTTP 200 verificado; vencimientos IIBB por año | `santafe_fiscal` |
| **Boletín Oficial SF** | B | Scraping (URLs predecibles) | existe | (futuro) |
| **datos.santafe.gob.ar** (CKAN) | — | API CKAN | ✅ verificado: NO responde JSON (vacío) → no usar como Tier A | — |
| **API Santa Fe / SIFCo** (clave fiscal) | Bloqueada | 403 / login clave fiscal | flujo asistido, no scraping | — |
| **RPJEC** (registro societario provincial) | Bloqueada | login / atencionvirtual | flujo asistido | — |
| **DDJJ web / padrón IIBB** | Bloqueada | clave fiscal | flujo asistido | — |

## Normas técnicas contables

| Fuente | Tier | Acceso | Connector |
|---|---|---|---|
| **FACPCE** (RT 6/9/16/17… estados contables) | B → estático | PDFs sueltos, índice 404 intermitente | recurso estático (mapa de RT + fecha de corte) |

## Marco de uso

- Argentina no tiene ley anti-scraping. Preferir SIEMPRE la API oficial (afip-ws, CKAN) sobre scraping.
- Respetar `robots.txt` y términos de cada sitio.
- Fuentes con login (clave fiscal, WSAA directo) → flujo asistido y consentido, nunca credenciales embebidas.
- **Honestidad técnica:** si una fuente es frágil o está bloqueada, el connector lo explica; no finge datos.
