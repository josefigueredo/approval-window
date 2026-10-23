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

*Pendiente: la completa quien coordina el proyecto después de la corrida.*
