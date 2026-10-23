# Mediciones

## Copilot CLI (2026-10-23)

- Versión: `GitHub Copilot CLI 1.0.103`.
- **Dónde lee las skills:** según `copilot skill --help`, las personales están en `~/.copilot/skills/` o en
  `~/.agents/skills/`. Verificado con `copilot skill list`: ya lista `jira-team-kit`, `jira-em` y `wow-*`, que
  `install.sh` de esos repos enlaza solo en `~/.agents/skills/`. Por eso `install.sh` de approval-window no necesita
  una carpeta propia para Copilot: con `~/.agents/skills/<name>` alcanza.
- **Cuánto espera una herramienta:** `copilot -p 'Run exactly this shell command…: sleep 150; echo SLEPT-OK' --allow-tool 'shell(sleep)' --allow-tool 'shell(echo)' -s`
  devolvió `SLEPT-OK`, y la corrida completa duró 167 s. Hasta 150 s no corta.
  - Medido en modo `-p`. En modo interactivo no se midió; se asume el mismo comportamiento.
  - Como no cortó a los 150 s, no se probaron 30 s ni 90 s.
- **Regla del plan:** `MAX_TIMEOUT = min(120, corte_de_copilot) - 20`. El corte de Copilot es de 150 s o más, así que
  queda **`MAX_TIMEOUT = 100`**, porque el límite lo pone Cursor (120 s). El chequeo de los 60 s pasa.

## Ventana real: verificación a mano (2026-10-23)

- `tools/preview.py`, primera corrida (antes del arreglo):
  - `irreversible` con los estilos `alert` y `edge` dio `approved`.
  - La primera ventana `tag` se cerró con `osascript exit -9`. La causa fue un `CGColor` pasado por el puente de JXA: el sistema mata el proceso (con una prueba aislada, la salida fue 137). Se reemplazó por un anillo `NSBox` hecho solo con `NSColor`; esa prueba sale con 0.
  - La persona marcó dos problemas visuales: el margen superior era menor que el izquierdo y la ventana era demasiado alta.
- `tools/preview.py`, segunda corrida (después del commit `b8011fb`): las 12 combinaciones de 4 niveles por 3 estilos abrieron y dieron `approved`, incluidos los 3 `tag`.
- Prueba de teclado con una ventana `irreversible`:
  - Primer intento: `approved`. La persona hizo clic en Apruebo **sin leer**. Es el reflejo que el proyecto quiere frenar, y aparece después de 12 ventanas iguales. Conclusión: la ventana sola no alcanza; las skills tienen que pedir aprobación pocas veces y solo cuando importa (ver la skill approval-window).
  - Segundo intento: `cancelled`. Enter no hizo nada, Tab+Espacio no aprobó y Escape canceló.

## De punta a punta en Copilot CLI y en Cursor (2026-10-23)

Se corrió `install.sh` en el HOME real. Quedaron `awin 0.1.0` en el PATH y las skills enlazadas.

- **Copilot CLI 1.0.103.** Al principio `copilot skill list` no cargó `approval-demo`: la descripción tenía un «: » sin
  comillas, que el YAML estricto rechaza. Claude Code no se quejaba. Se corrigió en `7a13ed0`, con un test que lo cubre.
  Las pruebas se lanzaron con `copilot -p … --allow-tool 'shell(python3)'`:
  - «borrá una nota»: el agente avisó que iba a aparecer la ventana, la persona aprobó y salió
    `done: deleted note "Shopping list"`. Tardó 50 s en total.
  - «archivá las notas»: la persona canceló y salió `not done: cancelled`. `notes.json` quedó sin cambios.
  - Detalle: el agente llamó a los botones «Approve» y «Cancel», pero en la ventana dicen «Apruebo» y «Cancelar».
- **Cursor**, con `cursor-agent v2026.10.22-27dcf5f`, el modelo GPT-5.6 Terra y una sesión interactiva lanzada con
  `run-in-cursor`, así que se registraron los hooks de Cursor:
  - «borrá una nota»: el agente avisó que iba a aparecer la ventana y mandó `demo.py delete-note` al fondo (31 s). La
    persona aprobó y salió `done: deleted note "Meeting notes"`.
  - «archivar las notas», en el mismo hilo: la persona canceló y salió `not done: cancelled`. `notes.json` quedó sin
    cambios.
- En los dos harnesses el agente esperó la respuesta y respetó tanto el «sí» como el «no».
