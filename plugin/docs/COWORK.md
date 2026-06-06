# Instalar y operar MCP-Contable en Claude Cowork

> Guía de instalación, actualización y **lecciones aprendidas** de poner el plugin a funcionar en
> Claude Cowork (Windows). Si volvés a este repo a actualizar el estudio, **leé esto antes de tocar
> el `.mcp.json` o la estructura del plugin.** Última actualización: 2026-06-06.

---

## 0. Estado actual (2026-06-06)

✅ **El plugin `mcp-contable` está instalado y operativo en Cowork.** Los 8 connectors conectan
(arca, ckan_nacional, ckan_juridico, infoleg, boletin_nacional, santafe_sin, santafe_fiscal, odoo).
El connector `odoo` autentica contra `gruponu_production` (NU Desarrollos, id=1). Circuito contable
completo vivo.

---

## 1. Cómo se instala en Cowork (flujo que funciona)

Cowork **NO** usa los comandos `/plugin marketplace add` (eso es del CLI de Claude Code). En Cowork
es por UI:

1. **Customize** (barra izquierda) → pestaña **Plugins**.
2. En **Complementos personales**, botón **"+"** → **Crear plugin** → **Agregar marketplace** →
   **Agregar desde un repositorio**.
3. Pegar la URL del repo: `https://github.com/GrupoNU/MCP-Contable` → **Sincronizar**.
4. Aparece el plugin **mcp-contable** → **Install** (scope **user**/personal).

### Para ACTUALIZAR tras un push
Customize → Plugins → chip **"MCP-Contable"** → **"..."** → **Buscar actualizaciones** → se activa
**Actualizar** → clic → **reiniciar Cowork** (cerrar del todo y reabrir).
- El menú muestra el **commit sincronizado**; si no coincide con el último de GitHub, "Buscar
  actualizaciones" lo refresca.
- **"Sincronizar automáticamente":** dejarlo **APAGADO** (actualización manual = control; con un
  sistema que toca la contabilidad real, no querés que cambie solo).

---

## 2. Requisitos en la PC

- **uv + Python 3.12** en el sistema. El `.venv` del repo se crea una vez: `cd plugin/connectors && uv sync`.
- **VPN Tailscale activa** (para `arca` → afip-ws, y `odoo` → odoo.gruponu.com, que van por la VPN).
- El repo en **`D:\git\MCP-Contable`** (el `.mcp.json` tiene rutas absolutas a esa ubicación).
- Archivo de secretos `~/.mcp-contable/secrets.env` con las credenciales de Odoo (ver §4).

---

## 3. ⚠️ LECCIONES APRENDIDAS — los problemas que costaron horas (y sus fixes)

> Cada uno fue un problema real distinto. El orden es el que fuimos descubriendo. **Si algo no
> conecta en Cowork, el error REAL está en los logs (§5), NO en lo que Cowork dice en el chat.**

### 3.1 Cowork instala SOLO desde repo Git (GitHub), no desde carpeta local
- La UI ("Add from a repository") pide una URL de repo. No hay opción de carpeta local.
- → El repo tiene que estar en GitHub. **Consecuencia:** el push deja de ser opcional, es requisito.

### 3.2 Repo privado NO instala bien en Cowork (bug conocido #28125)
- Con repo privado, "Agregar marketplace" falla en sincronizar.
- → Hicimos el repo **público**. (Verificamos antes que no hay secretos versionados.)

### 3.3 `source: "./"` (plugin en la raíz) NO funciona — debe ser subcarpeta
- Si el plugin apunta a la raíz del repo, Cowork da "Error al sincronizar el marketplace".
- → El plugin va en `plugin/` y el `marketplace.json` usa `source: "./plugin"` (patrón del
  marketplace oficial de Anthropic, que siempre apunta a subcarpetas).

### 3.4 Nombres de skill DUPLICADOS rompen el sync (y `claude plugin validate` NO lo detecta)
- Al consolidar 5 plugins en 1, renombramos los `cold-start-interview` de área a `perfil-<area>`
  pero **solo la carpeta** — el `name:` del frontmatter quedó en `cold-start-interview`.
- **Cowork valida los skills por el `name:` del frontmatter, no por la carpeta** → 5 con el mismo
  name → rechazo. El error solo aparece en el log (§5), no en el chat.
- → **Lección:** al renombrar un skill, cambiar SIEMPRE el `name:` del frontmatter. Los 18 names
  deben ser únicos.

### 3.5 `uv run` NO funciona en el sandbox de Cowork (el grande)
- Cowork lanza los connectors desde un **cwd contaminado** (la carpeta `outputs` de la sesión, llena
  de scripts `.py` sueltos del trabajo). Cuando `uv` intenta inspeccionar Python desde ahí, muere
  con `ModuleNotFoundError: No module named 'python.get_interpreter_info'` — con **cualquier**
  versión de Python (3.14, 3.12.12, incluso la del sistema 3.12.9).
- Síntoma: los connectors aparecen "still connecting" y nunca cargan las herramientas.
- → **FIX:** el `.mcp.json` NO usa `uv run`. Llama al **`python.exe` del `.venv` del repo
  directamente**:
  ```json
  "command": "D:\\git\\MCP-Contable\\plugin\\connectors\\.venv\\Scripts\\python.exe",
  "args": ["-m", "mcp_contable.<connector>.server"],
  "env": { "PYTHONPATH": "D:\\git\\MCP-Contable\\plugin\\connectors\\src", ... }
  ```
  El `.venv` se pre-crea una vez con `uv sync` en el repo. (Para desarrollo local fuera de Cowork sí
  se usa `uv run` normalmente.)

### 3.6 El sandbox de Cowork NO hereda las variables de entorno del sistema Windows
- `setx ODOO_API_KEY ...` NO sirve: el sandbox solo pasa las variables del bloque `env` del
  `.mcp.json`. Por eso `ODOO_URL`/`ODOO_DB` (en el `.mcp.json`) llegaban pero `ODOO_USER`/
  `ODOO_API_KEY` (en Windows) no → "authentication failed / falta API key".
- → **FIX:** el connector `odoo` lee `~/.mcp-contable/secrets.env` al importar
  (`_load_local_secrets()` en `odoo/server.py`). La API key vive SOLO en ese archivo local, **fuera
  del repo** (nunca en git, nunca en el repo público). Cowork sí lee archivos del disco.

---

## 4. El archivo de secretos de Odoo

`~/.mcp-contable/secrets.env` (en Windows: `C:\Users\<usuario>\.mcp-contable\secrets.env`):
```
ODOO_USER=mcp-contable@gruponu.com
ODOO_API_KEY=<la API key del usuario mcp-contable en Odoo>
ODOO_COMPANY_ID=1
```
- Formato `CLAVE=valor`, una por línea, `#` para comentarios.
- El connector `odoo` lo carga en `os.environ` al arrancar (solo completa lo que falte).
- **Nunca** versionar este archivo. La API key se genera en Odoo: usuario → Seguridad de la cuenta →
  Nueva clave de API. Ver `docs/ODOO.md` / notas de infra para el detalle del usuario `mcp-contable`.

---

## 5. Cómo DEBUGUEAR cuando algo no conecta (clave)

**El chat de Cowork da diagnósticos genéricos o equivocados** ("falta credencial", "verifica la
URL"). El error REAL está en los logs. Dos lugares:

1. **Logs por-connector** (lo más útil — el stderr del server al arrancar):
   ```
   C:\Users\<u>\AppData\Local\claude-cli-nodejs\Cache\...\mcp-logs-plugin-mcp-contable-<connector>\*.jsonl
   ```
   Buscar `"error":"Server stderr` — ahí está el traceback real de Python/uv.
2. **Log del host de Cowork** (errores de sync del marketplace, skills duplicados):
   ```
   C:\Users\<u>\AppData\Roaming\Claude\logs\cowork_host_loop_debug.log
   ```

Patrón de trabajo que funcionó: **leer el log → identificar el error exacto → reproducirlo
localmente corriendo el connector desde el cwd contaminado de Cowork → arreglar → verificar
reproduciendo → recién entonces pushear.** No adivinar; el log siempre tuvo la verdad.

Para reproducir el arranque como Cowork (sin uv, con el venv del repo):
```bash
cd "<carpeta outputs de la sesión de Cowork>"   # el cwd contaminado
PYTHONPATH="D:/git/MCP-Contable/plugin/connectors/src" \
  "D:/git/MCP-Contable/plugin/connectors/.venv/Scripts/python.exe" -c \
  "import asyncio; from mcp_contable.odoo import server as o; \
   print(asyncio.get_event_loop().run_until_complete(o.odoo_health())['data'])"
```

---

## 6. Resumen del `.mcp.json` actual (por qué es así)

- **command** = `python.exe` del venv del repo (no `uv`) → por §3.5.
- **args** = `["-m", "mcp_contable.<x>.server"]`.
- **env** = `PYTHONPATH` al `src/` + las vars no-secretas del connector (ej. `ODOO_URL`, `ODOO_DB`,
  `AFIP_WS_BASE_URL`). Los secretos van en el archivo local (§4), no acá.
- Rutas **absolutas** a `D:\git\MCP-Contable` (machine-specific; el repo debe estar ahí).
