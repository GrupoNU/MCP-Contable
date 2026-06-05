# Seguridad y confidencialidad — MCP-Contable

> Zero-retention de la documentación contable de NU. Última actualización: 2026-06-04.

## Principios

1. **Zero-retention de bodies.** `connectors/src/mcp_contable/common/http.py` NUNCA loguea
   request/response bodies, params, headers ni la URL completa (solo el host). Es el **único**
   camino HTTP sancionado: prohibido instanciar httpx directo en un server.
2. **Logs solo metadata.** Los `logs/` de los plugins registran solo metadata (tool, timestamp,
   source_tier) — nunca contenido contable de NU (facturas, DDJJ, montos, CUITs de terceros).
3. **Sin telemetría saliente.** El sistema no envía datos a terceros fuera de las fuentes
   oficiales consultadas explícitamente por una tool.
4. **Cache en memoria.** `common/cache.py` (TTLCache) vive solo en memoria de proceso; no
   persiste a disco. Se descarta al salir.

## Credenciales (NUNCA en el repo)

- El `.gitignore` ignora `.env`, `.env.*` (salvo `.env.example`), `*.key`, `*.pem`, `*.crt`,
  `*.p12`, `*.pfx`, `secrets/`, `credentials.json`.
- `.claude/settings.json` deniega `Read` sobre `.env` y sobre cualquier `*.key/*.crt/*.p12/*.pfx`.
- **Certificado AFIP:** el connector `arca` NO maneja el certificado. Reusa el microservicio
  `afip-ws` del VPS, donde el cert. de NU vive en `/opt/afip-ws/certs` (read-only, fuera de este
  repo). MCP-Contable nunca ve el certificado.

## Fuentes con login → flujo asistido (no scraping con credenciales embebidas)

- ARCA web services que requieren clave fiscal/WSAA directo (no el padrón vía afip-ws),
  API Santa Fe con clave fiscal, RPJEC, DDJJ web provincial: **NO** se scrapean con credenciales
  embebidas. Si hicieran falta, es un flujo asistido y consentido por el usuario.

## Datos de NU

- Las carpetas locales de NU (facturas, papeles de trabajo, DDJJ) se acceden vía Claude Cowork,
  NO se versionan en el repo. El `.gitignore` ignora `casos/`, `papeles-de-trabajo/`, `ddjj/`,
  `facturas/`, `*.confidencial`.

## Gate de seguridad de cierre (cada fase)

- Verificar que ningún dato de NU aparece en `logs/`.
- Verificar que `http.py` no fue modificado para loguear bodies.
- Verificar que no se versionó ningún `.env`, certificado ni clave.
