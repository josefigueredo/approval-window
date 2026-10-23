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
