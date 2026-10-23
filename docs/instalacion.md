# Instalación y primer uso, conversando con tu agente

Todo esto se hace conversando con tu agente (Claude Code, Codex, Cursor o Copilot CLI): le pedís las cosas y él corre los
comandos. Una cosa **no** es un prompt, y es a propósito: **el clic en Apruebo**. Es tuyo; si un agente pudiera
hacerlo, la ventana no serviría de nada.

> ¿Preferís ver cada comando? Está la [instalación detallada](instalacion-detallada.md). Para ver todo lo que hace, el
> [showcase](showcase.md).

| Paso | Qué hacés | Cómo |
|---|---|---|
| [1. Instalar](#1-instalar) | Dejar `awin` y las skills andando | Un prompt |
| [2. Probar que el comando responde](#2-probar-que-el-comando-responde) | Versión y rechazo de un pedido inválido | Un prompt |
| [3. Ver la ventana](#3-ver-la-ventana) | Una ventana de ejemplo por nivel | Un prompt + un clic tuyo |

> **Sobre las capturas.** La captura de instalación y la del paso 2 son salida **real** (con una carpeta de usuario de
> prueba y rutas acortadas). La de la ventana es una **maqueta**. [Origen de cada imagen](#de-dónde-sale-cada-captura).

---

## 1. Instalar

Necesitás macOS, `python3` 3.9 o más y el repo clonado. Abrí el repo en tu agente y pedile:

> Instalá approval-window: corré ./install.sh y decime qué enlazó. Si dice que no reemplaza algo, no lo borres: mostrame la ruta.

El script enlaza `awin` en `~/.local/bin` y las skills en `~/.agents/skills` (de ahí las leen Copilot CLI y los demás).
Si `~/.local/bin` no está en tu `PATH`, te lo avisa: agregarlo es cosa tuya.

## 2. Probar que el comando responde

> Corré `awin --version`. Después mandale a awin un pedido con una clave de más, por ejemplo "approved": true, y mostrame
> qué pasa. No le mandes ningún pedido válido: no quiero que se abra una ventana todavía.

Tiene que decir `awin 0.1.0` y, con la clave de más, rechazar el pedido con código 2 sin abrir nada.

## 3. Ver la ventana

> Usá la skill approval-demo y mostrame una ventana de cada nivel de reversibilidad.

Se abre una ventana por nivel, con un sonido. **Leelas y decidí vos**: Enter no aprueba, Escape cancela. El agente solo
te cuenta si aprobaste o cancelaste.

## Si algo falla

| Síntoma | Qué pasó | Qué le pedís al agente |
|---|---|---|
| `refusing to replace …: it is not a symlink` | Hay un archivo o carpeta real donde va un enlace | «Mostrame qué hay en esa ruta; lo muevo yo y volvemos a correr `./install.sh`» |
| `awin: command not found` | `~/.local/bin` no está en tu `PATH` | «Decime qué línea agregar a mi `.zshrc`» (la pegás vos) |
| `awin` sale con código 3 | No es macOS, falta `/usr/bin/osascript` o falló | «Corré `uname -s` y `ls /usr/bin/osascript`» |
| La skill no aparece en Copilot CLI | Falta el enlace en `~/.agents/skills` | «Corré `copilot skill list` y buscá approval-window» |

## De dónde sale cada captura

| Imagen | Origen |
|---|---|
| `terminal-instalar.png` | **Salida real** de `./install.sh` con un `HOME` temporal |
| `terminal-awin.png` | **Salida real** de `awin` con entradas inválidas (código 2, sin ventana) |
| `ventana-maqueta.png` | **Maqueta** del diseño aprobado (`docs/maquetas/ventana-estilos.html`); no es una ventana real |
