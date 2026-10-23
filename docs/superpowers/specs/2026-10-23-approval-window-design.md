# approval-window: ventana de aprobación para los CLI de las skills

Fecha: 2026-10-23. Estado: borrador para aprobar. Cuando exista el repo, este documento va a
`Harness/approval-window/docs/superpowers/specs/2026-10-23-approval-window-design.md` y se commitea.

## Intención

Los harnesses (Cursor, Copilot CLI, Claude Code) piden permiso para todo, y la gente termina diciendo que sí sin leer.
Este proyecto sirve para **humanizar los harnesses**: cuando el CLI de una skill va a hacer algo con consecuencias,
la persona ve una ventana nativa de macOS que dice en palabras simples qué va a pasar y si se puede deshacer. Recién
con un clic en «Apruebo» el CLI ejecuta. Con un clic alcanza, siempre que Apruebo no sea el botón por defecto.

Son dos piezas nuevas:

1. **El componente**: un comando global en el PATH que cualquier CLI de skill llama antes de escribir.
2. **La skill**: le enseña a un agente que construye o modifica el CLI de una skill a sumarle la ventana.

Hay además una **skill de prueba** para verificarlo de punta a punta.

## Objetivos

- Un único componente, instalado una vez, que cualquier CLI de skill puede llamar. Ninguna skill lleva su propia copia.
- Que la ventana se vea siempre con la misma estructura, para que la persona aprenda a leer una sola forma.
- Que el nivel de riesgo surja de un **hecho** declarado (la reversibilidad) y no de una opinión.
- Que funcione cuando el CLI lo lanza un agente dentro de Cursor o de Copilot CLI, sin terminal interactiva.

## No objetivos

- **No se tocan** jira-team-kit (`jtk`), confluence-team-kit (`ctk`) ni product-brain-mcp (`pbmcp`), ni ninguna
  skill publicada. Siguen con sus propias copias de la ventana. El desfase de pbmcp, que no tiene el arreglo de la
  ventana vacía, es un tema aparte.
- No hay soporte para Windows ni Linux: todo el equipo usa Mac.
- El componente no ejecuta la acción ni registra las escrituras. Lo único que hace es preguntar. Escribir y dejar el
  log es trabajo del CLI que lo llama.
- No hay modo de terminal (tipear «Apruebo N»): la ventana es el único camino. *Decisión mía; ver «Decisiones del
  diseñador».*

## Antiobjetivos (fallaría aunque funcione)

- Que se pueda aprobar sin un clic de una persona: con una tecla, con una variable de entorno, con un flag `--yes`,
  con un archivo de aprobación previa o con un valor por defecto. **Ninguno de esos caminos tiene que existir.**
- Que el CLI pueda meter HTML o JavaScript en la ventana. El CLI manda datos; el componente los escapa y los dibuja.
- Que todo termine en el nivel más alto «por las dudas», o en el más bajo «para que no moleste». Si pasa eso, la
  ventana vuelve a ser ruido, que es justo lo que este proyecto viene a evitar.
- Que una ventana vacía o a medio cargar se pueda aprobar.

## Restricciones

- macOS. La ventana es JXA (`osascript -l JavaScript`) con Cocoa y WebKit, igual que la que ya se probó en jtk
  (`Harness/jira-kanban/jkan/alert.js`).
- Python que corra también en `/usr/bin/python3` (3.9), solo con la biblioteca estándar y tests con `unittest`, como
  el resto de `Harness/`. TDD y conventional commits.
- El código, los mensajes del CLI y la skill van en inglés; la documentación para personas, en castellano rioplatense
  con el formato de `harness-docs`.
- El agente nunca hace clic ni automatiza la ventana. El hook `~/.claude/hooks/git-guardrails.sh` ya bloquea esos
  rodeos en Claude Code.
- Timeouts de los harnesses: Cursor corta una herramienta a los 120 s sin actividad (medido; por eso jtk usa 100 s).
  El de Copilot CLI **no está medido**.

## Lo que decidió el usuario

### Los harnesses

- El agente de Cursor y **GitHub Copilot CLI**, el harness de terminal. Quedan fuera el modo agente de Copilot en VS
  Code y el agente de Copilot en la nube, que no puede mostrar ventanas en la Mac.

### El componente

- Se instala como **comando global en el PATH**, igual que `jtk` o `wow`. Si no está instalado, la skill que lo
  necesita se niega a escribir y avisa.
- Lo llaman **los CLI de otras skills**.
- El CLI le pasa **datos, no HTML**:
  - El nombre de la skill.
  - La consecuencia en una frase, por ejemplo «Vas a crear 11 issues en Jira PLATE».
  - El nivel de reversibilidad y, de forma opcional, una línea que lo explica en palabras.
  - Unas pocas filas de resumen.
  - El detalle completo, plegado detrás de «Mostrar detalle».
  - El texto del botón, por ejemplo «Apruebo 11».
- Devuelve una sola respuesta: aprobado, cancelado o «no hay ventana disponible».

### La ventana

- Usa el estilo nativo de macOS y sigue el modo claro u oscuro del sistema.
- Hay **tres estilos disponibles**, y el CLI elige uno. Las maquetas aprobadas están en el brainstorm
  (`ventana-c-integrada.html`):
  - **alert** (C1): un ícono a la izquierda cuyo color marca el riesgo, y una línea bajo el título que lo dice en
    palabras.
  - **edge** (C2): una línea fina de color al costado del contenido.
  - **tag** (C3): una etiqueta con el riesgo arriba del título, y el borde de Apruebo teñido de ese color.
- Con **un clic alcanza**, pero **Apruebo nunca es el botón por defecto**: Enter no aprueba y Escape cancela.
- **Siempre suena al aparecer**: una sola vez, con el sonido de alerta del sistema (`NSBeep`), igual en los cuatro
  niveles. Respeta lo que la persona configuró: si tiene el volumen de alertas en cero o la Mac en silencio, no suena.
  La idea es que la persona la vea antes de que venza el timeout aunque esté en otra app.

### Los cuatro niveles de reversibilidad

El CLI declara el hecho y el componente elige el color. Nadie elige el color a mano.

| Nivel (valor) | Significado | Ejemplo | Color |
|---|---|---|---|
| `irreversible` | No hay vuelta atrás | Borrar sin papelera, mandar un mail | rojo |
| `partial` | Se revierte, pero deja rastro | Crear issues (salen notificaciones), editar un PR (queda historial) | naranja |
| `reversible_manual` | Se puede deshacer, pero a mano | Mover 10 tickets de estado | amarillo |
| `reversible_planned` | Hay un comando conocido para deshacer | Un apply con su undo | azul o gris |

Si el CLI declara `reversible_planned`, **tiene que pasar el comando para deshacer**, y la ventana lo muestra. Si no lo
pasa, el componente lo baja a `reversible_manual` y avisa por stderr.

**Quién lo ve** (`me`, `team`, `external`) no es un nivel: es una fila fija del resumen.

### La skill

La usa un agente cuando construye o modifica el CLI de una skill. Le enseña a:

1. Encontrar las acciones del CLI que tienen consecuencias.
2. Elegir el nivel de reversibilidad que corresponde.
3. Escribir la consecuencia en palabras simples.
4. Conectar la llamada al comando, con su test.

### La skill de prueba

Una skill de demostración nueva. **No se toca ninguna skill publicada.**

## Lo que queda a cargo de quien lo construye

- **El protocolo exacto** (nombres de campos, cómo entran los datos, códigos de salida). Lo que propongo, y que el
  builder puede ajustar:
  - El JSON entra por stdin o con `--spec <archivo>`.
  - El resultado es una palabra en stdout (`approved` o `cancelled`) más un código de salida: `0` aprobado,
    `1` cancelado, cerrado o vencido, `2` entrada inválida y `3` sin ventana disponible (no es macOS o falta
    `osascript`).
  - Si la entrada es inválida, nunca se abre la ventana.
- **Los límites:** cuántas filas de resumen y de qué largo, y cuánto detalle antes de cortar.
- **El timeout:** hay que **medir el de Copilot CLI** y elegir un valor por defecto que quede por debajo del menor de los
  dos harnesses. Hoy se sabe que tiene que ser de menos de 120 s por Cursor. El CLI puede pedir uno menor, pero nunca
  uno mayor que el máximo.
- **La instalación:** `install.sh` enlaza el comando en `~/.local/bin` y las skills en las carpetas de skills de
  Claude Code, Cursor y Copilot. **Hay que verificar dónde lee las skills Copilot CLI**: en `Harness/` no hay ningún
  instalador que lo resuelva todavía.
- **La skill de prueba:** un CLI chico con cuatro acciones falsas, una por nivel, que solo escriben en un archivo local
  propio después de la aprobación, y que usan los tres estilos.
- **El nombre:** propongo el repo `Harness/approval-window`, el comando `awin`, la skill `approval-window` y la skill
  de prueba `approval-demo`. El builder puede cambiarlos antes de crear el repo, si avisa.
- La estructura interna, el HTML y CSS de la ventana, y cómo se reparte el código entre Python y JXA.

## Hecho cuando

1. `awin` instalado en el PATH, con tests en verde en Python 3.12 y 3.9:
   - Escapa todo el texto.
   - Baja de nivel cuando falta el comando para deshacer.
   - Rechaza la entrada inválida sin abrir la ventana.
   - Devuelve los códigos de salida correctos.
   - No existe ningún camino para aprobar sin un clic.
2. Verificado a mano en la ventana real:
   - Enter no aprueba; Escape, cerrar la ventana o dejar que venza el tiempo dan «cancelled».
   - Apruebo arranca deshabilitado hasta que el contenido termina de cargar.
   - Se ven los tres estilos y los cuatro niveles, en modo claro y en modo oscuro.
3. La skill `approval-demo`, lanzada por el agente de **Cursor** y por el de **Copilot CLI** (en la terminal), muestra la ventana. Aprobar
   escribe y cancelar no escribe. Se prueba en los dos harnesses.
4. La skill `approval-window` le permite a un agente, empezando de cero, sumarle la ventana a un CLI de ejemplo con su
   test.
5. La documentación sigue el formato de `harness-docs` y pasa `hdoc check`.

## Decisiones del diseñador

Son decisiones mías: el usuario no las pidió y puede cambiarlas.

- Python 3.9 o superior con `unittest`, más JXA, como el resto de Harness.
- El estilo por defecto es **alert** (C1), porque es el más parecido a las alertas que la gente ya conoce del sistema.
- No hay modo de terminal. En Cursor y en Copilot casi nunca hay terminal interactiva, y con dos caminos hay dos cosas
  que mantener seguras.
- El comando para deshacer es obligatorio para `reversible_planned`; si falta, el nivel baja en lugar de dar error,
  para no frenar al CLI.
- Que quién lo ve (`me`, `team`, `external`) sea una fila fija y no un nivel.
- **Contra quién protege:** contra una persona que aprueba sin leer, que es el objetivo que pidió el usuario. Que el agente
  pueda rodear la ventana (un `awin` falso antes en el PATH, escribir sin pasar por el CLI) queda fuera de alcance. Para
  los clics y las teclas automáticas ya está el hook de guardrails. «No hay camino para aprobar sin un clic» quiere decir
  que `awin` no ofrece ninguna forma de aprobar sin clic.
- **Cómo testean los CLI que lo llaman:** cada CLI inyecta o simula su propia llamada a `awin` en sus tests (el mismo
  patrón que el parámetro `dialog` de `jkan/guard.py`). `awin` no trae modo de prueba. La skill enseña ese patrón.
- **Validación dentro de `awin`:** solo reglas estructurales. Se rechaza con salida 2 si falta un campo obligatorio,
  si un valor no es válido o si un texto se pasa del límite. Si falta el comando para deshacer, el nivel baja. Elegir
  bien el nivel es responsabilidad de la skill y se verifica con el criterio 4; `awin` no intenta adivinarlo.
- **Quién lo ve es obligatorio:** no hay valor por defecto. Si falta, la salida es 2.
- **Timeout:** se mide el de Copilot CLI. El valor por defecto es único y queda por debajo del menor de los dos harnesses.
  Si el de Copilot CLI da menos de 60 s, se vuelve a este diseño antes de seguir.
- **Criterio 4:** en el repo hay un CLI de ejemplo sin la ventana. Un subagente nuevo de Claude Code, que solo carga la
  skill, se la suma. Se da por cumplido si los tests del ejemplo pasan y el usuario revisa el diff.
- Las maquetas aprobadas se copian del scratchpad a `docs/maquetas/` del repo cuando se crea.
