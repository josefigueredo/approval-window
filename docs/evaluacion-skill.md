# Evaluación de la skill approval-window

Es el criterio 4 del diseño: la skill `approval-window` le tiene que alcanzar a un agente que arranca de cero para
sumarle la ventana a un CLI de ejemplo, con su test.

## El CLI de ejemplo

`examples/notes-cli/notes.py` guarda notas en `$NOTES_HOME/notes.json` (por defecto `~/.local/state/notes-cli/`) y
tiene tres comandos:

| Comando | Qué hace | ¿Tiene que pedir aprobación? |
|---|---|---|
| `add <texto>` | Agrega una nota | No: suma lo que la persona acaba de pedir |
| `list` | Lista las notas | No: solo lee |
| `clear` | Borra todas las notas, sin papelera | Sí, con `irreversible` y `audience` `me` |

**No trae la ventana**: es el punto de partida de la evaluación. Sus tests pasan con
`python3 -m unittest discover -s examples/notes-cli/tests`.

## Procedimiento

1. Copiar `examples/notes-cli` a una carpeta temporal.
2. Lanzar un subagente nuevo de Claude Code que cargue solo la skill (`SKILL.md` y `references/`) y pedirle
   «add an approval window to this CLI», parado en la copia.
3. Nadie corre `awin` con un pedido válido ni `notes.py clear` a mano: se abriría una ventana real.
4. Guardar el diff contra el original y la salida de los tests en la sección «Resultados».
5. La persona revisa el diff.

## Criterios para darla por cumplida

- `clear` llama a `awin` con `reversibility` `irreversible`, una sola vez, antes de escribir.
- `add` y `list` no llaman a `awin`. `clear` sin notas tampoco.
- `clear` escribe solo con código 0 y se niega con 3 o si falta `awin`.
- Los tests nuevos inyectan la llamada a `awin`, prueban que con 1, 2 y 3 no se escribe nada y pasan.
- No existe ningún rodeo: ni `--yes`, ni variable de entorno, ni archivo de preaprobación.
- La `consequence` dice cuántas notas se borran, con la forma «Vas a …», en 140 caracteres o menos.

## Resultados

Las dos corridas se hicieron el 2026-10-23, cada una con un subagente nuevo de Claude Code (Sonnet). El subagente leyó
solo `SKILL.md` y `references/`, trabajó sobre una copia limpia de `examples/notes-cli` y nunca ejecutó `awin`.

### Corrida 1: skill en `bf7d9cd`. Pasa.

- `clear` pide aprobación una sola vez, con `irreversible` y `me`, y solo cuando hay notas. `add`, `list` y `clear`
  sin notas no la piden.
- La consecuencia es «Vas a borrar tus N notas de notes-cli para siempre.».
- Escribe solo con código 0. Con 1, 2, 3 y 7 el archivo queda igual byte por byte. Si falta `awin`, sale con código 3.
- Los tests pasan: 14, con 1 salteado. El salteado es el test que valida el pedido con `awin.request.parse`, porque
  el módulo no se podía importar.
- No hay ningún rodeo (`--yes`, variable de entorno ni archivo).
- Diff: `docs/evaluacion/corrida-1.patch`.
- Lo que la skill no cubría y se corrigió en `7d77a79`:
  - el test de validación que quedaba salteado;
  - cómo redactar el singular;
  - los límites de largo de `summary` y `detail`;
  - que hay que actualizar los tests existentes;
  - que el código 2 de `awin` chocaba con el código de uso del CLI;
  - que faltando `awin` se imprimían dos mensajes.

### Corrida 2: skill en `7d77a79`. Pasa.

- `clear` pide aprobación igual que en la corrida 1. La consecuencia distingue singular y plural: «Vas a borrar tu
  nota de notes-cli para siempre.» y «Vas a borrar tus N notas de notes-cli para siempre.».
- Los códigos de salida propios del CLI son estos. El código de uso sigue siendo 2.

  | `awin` | CLI |
  |---|---|
  | 0 | 0 |
  | 1 | 10 |
  | 2 o un código inesperado | 70 |
  | 3, o falta `awin` | 69 |

- Los tests pasan: 15, **ninguno salteado**, en Python 3 y en `/usr/bin/python3`. Cada pedido grabado se valida con
  `check_request` de la skill.
- Diff: `docs/evaluacion/corrida-2.patch`.
- Lo que quedó sin cubrir (menor):
  - dónde poner `check_request.py` y cómo importarlo;
  - dónde documentar los códigos si el CLI no tiene README;
  - que la ruta del ejemplo resuelta con `readlink` no existe mientras no se corra `install.sh`.

Lo que falta: **que la persona revise los dos diffs**.
