# Instalación de MCP-Contable en Claude Cowork / Claude Code

> Guía paso a paso para instalar el estudio contable en **Claude Cowork** (o Claude Code) en la PC
> de NU Desarrollos. Para la guía de desarrollo (tests, etc.) ver `QUICKSTART.md`.

---

## 0. Qué vas a instalar

Un **marketplace local** con 5 plugins (1 puerta de recepción + 4 áreas especialistas) que corren
sobre la suscripción Claude del usuario (costo IA $0) y acceden a las carpetas locales de NU + las
fuentes oficiales vía connectors MCP.

---

## 1. Requisitos (una sola vez)

1. **Claude Code / Cowork** instalado y logueado.
2. **Python 3.12** y **uv** (gestor de paquetes). Verificá:
   ```powershell
   uv --version
   python --version
   ```
   uv se instala desde https://docs.astral.sh/uv/ si falta.
3. **Dependencias de los connectors instaladas:**
   ```powershell
   cd D:\git\MCP-Contable\connectors
   uv sync
   ```
   Esto crea el entorno `.venv` y deja los 7 connectors listos para correr.
4. **Solo para el connector `arca` (constancia/padrón AFIP):** la PC donde corre Cowork debe estar
   conectada a la **VPN Tailscale de GrupoNU**. El connector NO habla con AFIP directo: llega al
   microservicio `afip-ws` del VPS (donde vive el certificado de NU) por la red Tailscale
   (`100.88.25.41`). **Es la misma VPN que ya usás para el MCP `supabase-db`** — si ese ya te
   funciona, `arca` también. Los otros 6 connectors usan fuentes públicas y **no requieren VPN**.
   Si Tailscale se desconecta, `arca` avisa con un error claro y los demás siguen andando.

---

## 2. Agregar el marketplace

En Claude Code / Cowork, agregá el marketplace apuntando a la **carpeta raíz** del repo (la que
contiene `.claude-plugin/marketplace.json`):

```
/plugin marketplace add D:\git\MCP-Contable
```

Verificá que se agregó:

```
/plugin marketplace list
```

Debería aparecer el marketplace **`mcp-contable`** con sus 5 plugins.

---

## 3. Instalar los plugins

Instalá los que necesites (el nombre del marketplace es `mcp-contable`). Se recomienda instalar la
**puerta de recepción primero** y al menos un área:

```
/plugin install estudio-contable@mcp-contable
/plugin install impuestos-liquidaciones@mcp-contable
/plugin install sueldos@mcp-contable
/plugin install registracion-estados-contables@mcp-contable
/plugin install societario-cumplimiento@mcp-contable
```

> También podés usar el menú interactivo escribiendo `/plugin` y navegando a **Discover**.

Verificá que no haya errores de carga: abrí `/plugin` y mirá la pestaña **Errors** (debería estar
vacía). Si un connector falla, casi siempre es la ruta del `.mcp.json` (ver §6).

---

## 4. Configurar el connector `arca` (AFIP)

El connector `arca` necesita saber dónde está el microservicio `afip-ws`. Creá el archivo
`connectors\.env` (NO se versiona) con:

```
AFIP_WS_BASE_URL=http://100.88.25.41:8001
```

(Esa es la IP Tailscale del VPS. Requiere VPN Tailscale activa.) Si no configurás esto, los otros
connectors funcionan igual; solo `arca` devolverá un error explicado pidiendo la configuración.

---

## 5. Primer uso — configurar el perfil del estudio

Antes de trabajar, corré **una vez** la entrevista de configuración global, que captura el perfil de
NU (rol, CUIT, régimen, jurisdicciones, carpetas locales) para que todas las áreas lo lean:

```
/estudio-contable:cold-start-interview
```

Después ya podés usar la puerta de recepción para cualquier consulta:

```
/estudio-contable:recepcion
```

…o ir directo a un área, por ejemplo:

```
/impuestos-liquidaciones:consulta-impuestos
/sueldos:consulta-sueldos
/societario-cumplimiento:consulta-cumplimiento
/registracion-estados-contables:consulta-registracion
```

Cada área tiene además sus skills de fuente (`buscar-normativa-...`, `analizar-norma-...`) y su
propio `cold-start-interview` si querés afinar el perfil de esa área.

---

## 6. Verificación rápida y problemas comunes

**Verificar que un connector arranca** (smoke test, desde PowerShell):
```powershell
uv run --directory D:\git\MCP-Contable\connectors python -m mcp_contable.arca.server
```
Si ves el banner de FastMCP, arrancó bien (Ctrl+C para salir).

**Verificar `arca` en vivo** (con VPN Tailscale activa):
```powershell
curl http://100.88.25.41:8001/health
```
Debería responder `{"status":"ok",...}`.

**Problemas comunes:**
- **Un connector no carga / "command failed":** revisá que la ruta absoluta en el `.mcp.json` del
  plugin (`D:\git\MCP-Contable\connectors`) coincida con dónde está el repo en esta PC. Las rutas
  son **absolutas a esta máquina** a propósito (las relativas se rompen al instalar). Si moviste el
  repo, actualizá la ruta en los `.mcp.json`.
- **Warning de `VIRTUAL_ENV`:** si tenés un venv global de Python activo, uv puede mostrar un
  warning ("does not match the project environment"). Es inofensivo: uv usa el `.venv` del proyecto.
- **`arca` devuelve "afip-ws not configured":** falta el `connectors\.env` con `AFIP_WS_BASE_URL`
  (§4).
- **`arca` devuelve "afip-ws unavailable":** no estás conectado a la VPN Tailscale, o el afip-ws
  está caído.

---

## 7. Recordatorio importante

**Toda salida del estudio es un BORRADOR para revisión de un contador matriculado.** El sistema
nunca afirma un monto, alícuota, tope o vencimiento sin fuente verificada (si no la tiene, lo marca
`[verify]`). Un profesional revisa, verifica las cifras y asume la responsabilidad.
