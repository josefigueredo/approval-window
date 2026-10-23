# Referencia del protocolo

`awin` lee un pedido JSON (por stdin o con `--spec ARCHIVO`), muestra la ventana y contesta con una palabra y un código
de salida. El que llama manda **datos, nunca HTML**: todo texto se escapa y la vista web corre sin JavaScript.

## El pedido

Las claves desconocidas se rechazan (código 2).

| Clave | Tipo | Obligatoria | Límite / valores |
|---|---|---|---|
| `skill` | str | sí | 1–40 caracteres; va en la barra de título |
| `consequence` | str | sí | 1–140 caracteres; el encabezado |
| `reversibility` | str | sí | `irreversible`, `partial`, `reversible_manual`, `reversible_planned` |
| `audience` | str | sí | `me`, `team`, `external` |
| `risk_note` | str | no | hasta 140; si falta, el texto por nivel de abajo |
| `undo` | str | obligatoria con `reversible_planned` | hasta 200; se muestra como una fila |
| `summary` | lista de `[etiqueta, valor]` | no | hasta 6 filas; etiqueta hasta 30, valor hasta 100 |
| `detail` | lista de str | no | líneas de hasta 300; pasadas las 200, se corta con «… y N más» |
| `approve_label` | str | no | 1–24 caracteres; por defecto `Apruebo` |
| `style` | str | no | `alert` (por defecto), `edge`, `tag` |

Cualquier texto (también las etiquetas, los valores de `summary` y las líneas de `detail`) se rechaza con código 2
si tiene un carácter de control (U+0000–U+001F, o sea también saltos de línea y tabulaciones, o U+007F), un surrogate
suelto o un carácter que invierte la dirección del texto (U+202A–U+202E, U+2066–U+2069). `skill`, `consequence` y
`approve_label` no pueden ser solo espacios.

Texto por defecto de `risk_note`:

| Nivel | Texto |
|---|---|
| `irreversible` | No se puede deshacer. |
| `partial` | Se puede revertir, pero deja rastro. |
| `reversible_manual` | Se puede deshacer, pero a mano. |
| `reversible_planned` | Se puede deshacer con un comando. |

La fila «Lo ve» según `audience`: `me` «Solo vos», `team` «Tu equipo», `external` «Gente de afuera».

Colores por nivel: `irreversible` `#ff3b30`, `partial` `#ff9f0a`, `reversible_manual` `#ffcc00`, `reversible_planned` `#0a84ff`.

`reversible_planned` sin `undo` no es un error: se muestra como `reversible_manual` y `awin` avisa por stderr
`awin: reversible_planned without undo; shown as reversible_manual`.

## La respuesta

Una palabra por stdout (`approved` o `cancelled`), solo con código 0 o 1.

| Código | Significa |
|---|---|
| `0` | `approved`: la persona hizo clic en Apruebo |
| `1` | `cancelled`: canceló, cerró, venció el tiempo o falló algo |
| `2` | Entrada inválida: la ventana nunca se abre; el motivo va por stderr |
| `3` | No hay ventana disponible: no es macOS, falta `/usr/bin/osascript` o `osascript` falló |

## Opciones

| Opción | Efecto |
|---|---|
| `--spec ARCHIVO` | Lee el pedido de un archivo en vez de stdin |
| `--timeout SEGUNDOS` | Espera menos; nunca más que el máximo (100 s) |
| `--version` | Imprime `awin 0.1.0` |

El código 0 quiere decir aprobado solo junto con `approved` en stdout. `-h` y `--version` también salen con 0 y no
imprimen `approved`; el cableado nunca pasa opciones. Las opciones no se abrevian: `--v` o `--t 30` salen con 2.

El máximo de 100 s sale de una medición: Cursor corta una herramienta a los 120 s y Copilot CLI no cortó a los 150 s
([mediciones](mediciones.md)).

## Qué garantiza y qué no

- Nada aprueba sin un clic: no hay `--yes`, variable de entorno, archivo de preaprobación ni botón por defecto. Enter no
  aprueba; Escape, cerrar, un fallo y el tiempo vencido son `cancelled`.
- Apruebo está deshabilitado hasta que la página terminó de cargar. Suena un `NSBeep` al abrirse, en todos los niveles.
- **No** garantiza que la persona lea: ver el [caso medido](showcase.md#4-lo-que-midió-la-ventana-real).
