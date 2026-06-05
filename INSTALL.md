# Instalación de MCP-Contable en Claude Cowork

> Guía paso a paso para instalar el estudio contable en **Claude Cowork** en la PC de NU
> Desarrollos. Para desarrollo (tests, etc.) ver `QUICKSTART.md`.

---

## 0. Qué vas a instalar

**Un solo plugin** llamado `mcp-contable` que trae el estudio contable completo: una **recepción**
que clasifica tu consulta y la deriva al área correcta, más las 4 áreas especialistas (impuestos/
liquidaciones, sueldos, registración/estados contables, societario/cumplimiento) y los 7 connectors
a fuentes oficiales. Corre sobre tu suscripción Claude (costo IA $0) y accede a las carpetas locales
de NU + las fuentes oficiales.

> **Importante:** Cowork instala plugins **desde un repositorio Git (GitHub)**, no desde una carpeta
> local. Por eso el repo tiene que estar en GitHub (puede ser privado).

---

## 1. Requisitos (una sola vez en esta PC)

1. **Claude Cowork** instalado y logueado.
2. **Python 3.12** y **uv** (gestor de paquetes), accesibles en el PATH:
   ```powershell
   uv --version
   python --version
   ```
   uv se instala desde https://docs.astral.sh/uv/ si falta. Cowork lanza los connectors con `uv`,
   así que tiene que estar en el PATH (en esta PC ya lo está: `C:\Users\grupo\.local\bin`).
3. **Para el connector `arca` (constancia/padrón AFIP):** estar conectado a la **VPN Tailscale de
   GrupoNU** — es la **misma VPN que ya usás para el MCP `supabase-db`**. Si ese te funciona, `arca`
   también. Los otros 6 connectors usan fuentes públicas y no requieren VPN.

---

## 2. Agregar el marketplace en Cowork

1. En Cowork, abrí la barra lateral izquierda → **Customize**.
2. Andá a la pestaña **Plugins**.
3. En **Personal plugins**, hacé clic en **"+"** → **Add marketplace** → **Add from a repository**.
4. Pegá la URL del repo:
   ```
   https://github.com/GrupoNU/MCP-Contable
   ```
   (Si el repo es privado, Cowork te pedirá autorizar el acceso a GitHub.)

---

## 3. Instalar el plugin

Una vez agregado el marketplace `mcp-contable`, vas a ver **un plugin: `mcp-contable`**. Hacé clic en
**Install** (scope **user** / personal por defecto, para tenerlo disponible en cualquier sesión).

---

## 4. Configurar el connector `arca` (AFIP)

El connector `arca` necesita la URL del microservicio `afip-ws`. En la carpeta del repo, creá
`connectors\.env` (NO se versiona) con:

```
AFIP_WS_BASE_URL=http://100.88.25.41:8001
```

(IP Tailscale del VPS; requiere VPN activa.) Sin esto, los otros connectors funcionan igual; solo
`arca` devolverá un error explicado.

> Nota: la primera vez que se usa un connector, `uv` crea el entorno Python del proyecto
> automáticamente (puede tardar unos segundos esa primera vez).

---

## 5. Primer uso — configurar el perfil del estudio

Corré **una vez** la entrevista de configuración global (perfil de NU: rol, CUIT, régimen,
jurisdicciones, carpetas locales):

```
/mcp-contable:cold-start-interview
```

Después usá la puerta de recepción para cualquier consulta:

```
/mcp-contable:recepcion
```

…o invocá un área directamente, por ejemplo:

```
/mcp-contable:consulta-impuestos
/mcp-contable:consulta-sueldos
/mcp-contable:consulta-cumplimiento
/mcp-contable:consulta-registracion
```

Skills de apoyo por área: `buscar-normativa-fiscal` / `analizar-norma-fiscal` (y sus equivalentes
laboral/contable/societaria), y `perfil-impuestos` / `perfil-sueldos` / `perfil-registracion` /
`perfil-societario` para afinar el perfil de cada área.

---

## 6. Verificación y problemas comunes

**Verificar `arca` en vivo** (con VPN Tailscale activa), desde PowerShell:
```powershell
curl http://100.88.25.41:8001/health
```
Debería responder `{"status":"ok",...}`.

**Problemas comunes:**
- **Un connector no carga:** revisá que `uv` esté en el PATH (`uv --version`). Cowork lo lanza por
  nombre. Las rutas de los connectors usan `${CLAUDE_PLUGIN_ROOT}` (la carpeta donde Cowork instaló
  el plugin), así que no dependen de dónde esté el repo.
- **`arca` devuelve "afip-ws not configured":** falta `connectors\.env` con `AFIP_WS_BASE_URL` (§4).
- **`arca` devuelve "afip-ws unavailable":** no estás conectado a la VPN Tailscale, o el afip-ws
  está caído.
- **Warning de `VIRTUAL_ENV`:** inofensivo; uv usa el `.venv` del proyecto.

---

## 7. Actualizar el plugin

Cuando haya cambios, se pushean al repo de GitHub y en Cowork: **Customize → Plugins → mcp-contable
→ Update** (re-sincroniza desde el repo).

---

## 8. Recordatorio importante

**Toda salida del estudio es un BORRADOR para revisión de un contador matriculado.** El sistema
nunca afirma un monto, alícuota, tope o vencimiento sin fuente verificada (si no la tiene, lo marca
`[verify]`). Un profesional revisa, verifica las cifras y asume la responsabilidad.
