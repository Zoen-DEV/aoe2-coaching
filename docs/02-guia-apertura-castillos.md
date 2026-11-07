# Idea 2: AoE2 Coaching (guía de apertura hasta Castillos)

- **Estado:** v4 instalada: **panel de AoE2C** (dashboard), guía de **Scouts 21** y elección de guía desde el panel, con 5 mapas. Probado con tests de código y capturas en memoria; **falta probarlo en una partida** (ver "Cómo probarlo en el juego").
- **Tipo de mod:** mapa aleatorio con script XS, más un overlay en Python (PySide6)
- **Juego:** Age of Empires II: Definitive Edition
- **Código:** [content/guias/build.py](../content/guias/build.py) y [apps/desktop/aoe2c.py](../apps/desktop/aoe2c.py) (el programa único: overlay y panel)

## Qué hace

Son copias de mapas oficiales que cargan un script XS: **"[AoE2C] Arabia"**, **"[AoE2C] Arena"**, **"[AoE2C] Black Forest"**, **"[AoE2C] Runestones"** y **"[AoE2C] Fortress"**. El script sigue la apertura elegida (**Fast Castle 27+2** o **Scouts 21**) y, cada segundo, vuelca el estado en un archivo. **AoE2C**, un programa aparte, lee ese archivo y dibuja la guía encima del juego; además tiene un **panel** (dashboard) con estadísticas y ajustes.

### El panel de AoE2C (dashboard)

Es la ventana principal del programa, al estilo de las apps compañeras de los juegos competitivos (Blitz y similares). Se abre sola al acabar la animación de inicio (salvo que haya una partida en curso). Es una ventana normal de Windows, con la barra de título oscura: sale en la barra de tareas y **no se pone encima del juego**.

- **La ✕ no cierra el programa:** esconde el panel y AoE2C sigue en la bandeja (la primera vez, un aviso de Windows lo recuerda). Clic en el icono de la bandeja → vuelve el panel.
- **Cerrar AoE2C del todo:** clic derecho en el icono de la bandeja → **Cerrar AoE2C**, o el botón **Cerrar AoE2C** abajo a la izquierda del panel.
- **Una sola copia:** si se abre el acceso directo con AoE2C ya abierto, no arranca otra copia; la que está abierta muestra su panel.
- Arriba a la derecha, **Abrir AoE2** lanza el juego con Steam (se desactiva si el juego ya está abierto).

Páginas (barra lateral):

| Página | Qué tiene |
|---|---|
| **Inicio** | La guía activa (con aviso si los mapas aún no la cargan), el estado del juego (cerrado, abierto, partida en curso con el paso), tus números con la guía activa (partidas, mejor marca, media de las últimas 10 frente a las 10 anteriores, % de guías completadas), la última partida y los pasos para jugar. |
| **Estadísticas** | Una pastilla por guía y, debajo, el mismo contenido que la ventana del historial (resumen general, evolución, dónde pierdes tiempo, detalle de cada partida y Borrar). |
| **Guías** | Una tarjeta por guía: descripción, nivel, pasos, meta, mapas recomendados, "Ver pasos" y **Usar esta guía**. Debajo, las que vendrán (Arqueros, Drush FC, Hombres de armas → Arqueros, Águilas). |
| **Mapas** | Una tarjeta por mapa con su imagen, tipo, descripción, guías recomendadas y estado (Instalado, Hay una versión nueva, No instalado). Botones **Instalar / Actualizar / Quitar** y **⤓** para guardar una copia del `.rms` y su imagen en otra carpeta. |
| **Ajustes** | Idioma (español / inglés), abrir el panel al iniciar, iniciar con Windows; y de la guía en partida: posición, opacidad, pasos de "A continuación", aviso de casas, abrir el historial al terminar y la pestaña del historial. Al final, botones para abrir las carpetas del juego, del perfil y del mod. |

Los cambios de Ajustes se aplican al momento (el panel y el overlay comparten las preferencias en `%APPDATA%\AoE2Coaching\config.json`). El idioma cambia el panel y los menús; las guías y la tarjeta de la partida siguen en español.

### Elegir la guía

Todos los mapas cargan el mismo script, `aoe2c_guia.xs`, de la carpeta `xs` del perfil. **Usar esta guía** copia encima el script de la guía elegida (`guia_fast_castle.xs` o `guia_scouts.xs`). Vale desde la siguiente partida, sin reiniciar el juego. El script escribe en el archivo de estado el **código de la guía**, así el overlay sabe qué guía se está jugando aunque el mapa sea el mismo.

### El overlay (por defecto)

Es una tarjeta oscura y opaca a la derecha, justo encima del marcador de puntos; desde su menú se puede pasar a la izquierda. Contiene:

- **Cabecera:** nombre de la build order, reloj de la partida, "Paso 5 de 16", una pastilla de ritmo (verde "A tiempo", ámbar "+22 s", azul "−10 s") y una barra de progreso general.
- **El paso actual:** icono, título, objetivo con cuenta atrás ("faltan 0:42" o "12 s tarde"), la instrucción completa y una barra por condición (Casas 2/3, Molino 0/1…).
- **"A continuación":** los 3 pasos siguientes con su hora de referencia. Los pasos hechos no se muestran.
- **Al completar un paso,** aparece unos segundos un aviso verde con la hora y el desfase, y la tarjeta del paso nuevo entra con una animación.
- **Aviso de casas** en rojo, y al llegar a Castillos un resumen que desaparece a los 90 s.

La tarjeta deja pasar los clics al juego y no le quita el foco. Solo se ve cuando se cumplen dos cosas:

- **Age of Empires está en primer plano.** Si minimizas el juego o cambias a otro programa, el overlay se oculta. Se comprueba la ventana activa cada 0,25 s.
- **Hay una partida en curso en un mapa [AoE2C].** El juego actualiza el archivo más de una vez por segundo. Si pasan 4 s sin datos nuevos (has salido de la partida), el overlay se oculta y vuelve a su estado inicial: desplegado y sin guía cargada, listo para la siguiente partida. El programa sigue en la bandeja. Con el juego en pausa también se oculta, y reaparece al reanudar.

**Plegar y desplegar:** el botón **›** de la cabecera desliza la tarjeta fuera de la pantalla, en 0,28 s a 60 fps. La tarjeta se dibuja una sola vez en memoria y durante la animación solo se mueve la ventana. Queda una pestaña pegada al borde con el número del paso actual; al pulsarla, la tarjeta vuelve. El lado se recuerda entre partidas; al empezar una partida nueva, la tarjeta sale siempre desplegada.

El icono de la bandeja es el mismo que el del acceso directo del escritorio (el casco del juego, sacado de `AoE2DE_s.exe`; si no se encuentra el juego, un check azul). Dice qué está leyendo y tiene el mismo menú.

**Al abrir el programa** aparece unos 3 s en el centro de la pantalla una tarjeta con el icono y "AoE2 Coaching": entra con un leve zoom, se queda un momento y se desvanece. No recibe clics ni quita el foco.

**Para usarlo:**
- Ábrelo con el acceso directo del escritorio **"AoE2 Coaching"** (o con `apps/desktop/Iniciar overlay.bat`), antes o durante la partida. No se ve nada hasta que hay una partida en un mapa [AoE2C].
- Ciérralo con el **botón de menú (⋯)**, arriba a la derecha de la tarjeta → **"Cerrar overlay"**. El mismo menú permite mostrar u ocultar la guía y pasarla a la izquierda o a la derecha. Los botones y la pestaña son lo único que recibe clics; el resto deja pasarlos al juego. El menú se abre sin bloquear el overlay. También está el mismo menú en el icono de la bandeja (en Windows 11, tras la flecha "^" junto al reloj) y, si no se ve el overlay, `apps/desktop/Cerrar overlay.bat`.
- El borde superior de la tarjeta queda fijo durante toda la partida, calculado con la altura máxima de la guía, para que los botones no se muevan cuando la tarjeta cambia de tamaño.
- El juego debe estar en **ventana sin bordes** o en ventana: en pantalla completa exclusiva ninguna ventana puede dibujarse encima.
- Necesita PySide6 (`py -m pip install PySide6==6.12.0`).

Para ver el diseño sin jugar: `py overlay.py --demo` (simula una partida que avanza un paso cada 5 s).

### El historial de aperturas

El overlay guarda cada partida en `%APPDATA%\AoE2Coaching\historial.json`, sin tocar el script XS. Por partida anota la hora de cada paso de la guía y cuatro hitos: **clic en Feudal, llegada a Feudal, clic en Castillos y llegada a Castillos**.

- **Al terminar la partida** (cuando el juego deja de enviar datos durante 4 s) se abre sola la ventana del historial, con la partida recién jugada elegida y un aviso: hora de Castillos, si es tu mejor marca, la diferencia con tu media y el tramo donde más perdiste. Al volver a la partida se cierra sola.
- **Fuera de partida** (menú principal, sala, pantalla de puntuación), con el juego delante, aparece una pestaña **HISTORIAL** pegada al borde de la pantalla, a media altura, en el mismo lado que la guía. Al pulsarla se abre el historial. Se puede quitar desde el menú (⋯ o bandeja) → "Pestaña del historial fuera de partida".
- **Desde el menú** (⋯ o bandeja) → "Ver historial de aperturas", en cualquier momento.
- **En la tarjeta final** de la guía ("¡Llegaste a Castillos!") se añade una línea: nueva mejor marca o tu mejor, y tu media.

La ventana recibe clics y la rueda del ratón sin quitarle el foco al juego, y se cierra con la ✕. A la izquierda tiene una **barra lateral** y a la derecha el panel con los datos:

- **Barra lateral:** arriba, **Resumen general**; debajo, las partidas de la más reciente a la más antigua, con su hora de Castillos y la diferencia con tu media (o ★ si es tu mejor marca). Al pulsar una se ve su detalle; al pulsar Resumen general, se vuelve a la comparativa.
- **Resumen general** (sin partida elegida, como al abrir desde la pestaña o el menú):
  - **Cuatro fichas** con tu media de cada hito en las últimas 10 partidas, la diferencia con las 10 anteriores y tu mejor marca.
  - **Evolución:** la llegada a Feudal y a Castillos en las últimas 20 partidas, con la referencia en discontinua. Al pasar el ratón por una partida se ven sus valores; al pulsarla, se elige.
  - **Dónde pierdes tiempo:** los 5 tramos donde más tiempo pierdes de media en las últimas 10 partidas. El tramo de un paso es cuánto creció el retraso desde el paso anterior, así un retraso arrastrado no se cuenta dos veces.
- **Una partida** (al acabarla se abre así, con el aviso):
  - **Cuatro fichas** con sus hitos, su diferencia con tu media (verde si vas más rápido), tu mejor marca y la referencia.
  - **Evolución** con la partida marcada, para ver dónde queda frente a las demás.
  - **Paso a paso:** hora, diferencia con la referencia y tramo; el tramo más lento sale resaltado. El botón **Borrar** (con un segundo clic para confirmar) quita la partida, por ejemplo una de prueba.

**Cómo se mide:**
- El clic y la llegada a cada edad se anotan al ver cambiar el estado de la tecnología en el archivo del juego, con 1 s de precisión. Si el overlay se abrió tarde y no vio el cambio, el clic se toma de la hora del paso equivalente de la guía; la llegada a Feudal, que no tiene paso propio, queda vacía en lugar de inventarse.
- Una partida nueva empieza cuando cambia el mapa o el reloj del juego vuelve atrás. Si cierras y abres el overlay a mitad de partida, sigue el mismo registro.
- Si jugaste con el overlay cerrado, al abrirlo se importa la última partida (solo la última: el juego sobrescribe el archivo en cada partida).
- Las partidas en las que no se completó ningún paso no se guardan.
- **Limitación:** el juego no avisa de la pausa, así que pausar también abre el historial (y al reanudar se cierra).

Para ver el historial sin jugar: `py overlay.py --demo` termina con el historial abierto, con datos inventados que no se guardan. `py overlay.py --captura DIR` también genera `historial.png` (resumen general), `historial_partida.png` (una partida recién terminada) e `historial_vacio.png`.

### El panel del juego (opcional)

Con `"panel_juego": true` en el JSON, la guía también se muestra en el panel de instrucciones nativo, arriba en el centro. Su posición y su aspecto no se pueden cambiar: es un componente interno del juego (`UIWidgetInstructionsPanel`), no un archivo de interfaz modificable.

```
Fast Castle 27+2 · Paso 5 de 16 · vas 22 s tarde
[x] 3. Campamento y 4 leñadores · 3:21
[x] 4. Primer jabalí · 3:52 (+22 s)
» 5. Con el aldeano 12, construye una casa y un molino junto a las bayas.
     Los aldeanos 12 a 16 recolectan bayas. (ref. 5:40)
     Casas 2/3 · Molino 0/1 · Bayas 1/5
[ ] 6. Segundo jabalí, 14 en comida · 6:25
[ ] 7. Segundo campamento, 9 leñadores · 8:35
[ ] 8. Campamento minero, 3 en oro · 9:55
```

- **Cabecera:** la build order, el paso actual y el ritmo según el último paso hecho ("a tiempo", "vas 22 s tarde" o "vas 10 s adelantado", con 20 s de margen).
- **Los últimos pasos hechos** (`pasos_hechos_visibles`, 0 por defecto), con la hora a la que se cumplieron y el desfase si pasa del margen.
- **El paso actual,** con la instrucción completa, la hora de referencia y el progreso en vivo.
- **Los 3 pasos siguientes,** con su hora de referencia.
- **El icono** del panel es el del edificio o la unidad del paso actual.
- **Sonido:** el aviso normal de instrucciones del juego, cada vez que se completa un paso.
- **Aviso de casas:** un segundo panel en rojo, justo debajo, cuando quedan 2 huecos de población o menos y no hay ninguna casa en obra.

Al llegar a Castillos, el panel muestra los últimos pasos, la hora de llegada frente a la referencia y el siguiente objetivo, y desaparece a los 90 s.

## Decisiones

| Decisión | Elegido |
|---|---|
| Build order | Fast Castle (27+2) y Scouts 21; se elige en el panel |
| Elección de guía | Un script común (`aoe2c_guia.xs`) que el panel sustituye, en vez de un mapa por guía |
| Panel | Ventana normal (no encima del juego); la ✕ la esconde en la bandeja |
| Civilización | Genérica (empieza con 3 aldeanos y granjas normales) |
| Mapas base | Arabia, Arena, Black Forest, Runestones y Fortress (`mapas.json`) |
| Formato | Mapa aleatorio con XS (opción A del diseño inicial) |
| Interfaz | Un solo panel con 2 pasos hechos, el actual y 3 siguientes (configurable en el JSON) |
| Extra | Ritmo respecto a un tiempo de referencia, y aviso de casas |

## Los pasos

La fuente es [build_orders/fast_castle_27_2.json](../content/guias/build_orders/fast_castle_27_2.json). Los aldeanos se numeran contando los 3 iniciales.

| # | Ref. | Título en el panel | Se marca hecho cuando |
|---|---|---|---|
| 1 | 0:35 | 2 casas | 2 casas terminadas |
| 2 | 1:20 | 6 pastores | 6 pastores |
| 3 | 3:10 | Campamento y 4 leñadores | 1 campamento maderero y 4 leñadores |
| 4 | 3:30 | Primer jabalí | 1 cazador o más |
| 5 | 5:40 | Casa, molino y 5 en bayas | 3 casas, 1 molino y 5 recolectores |
| 6 | 6:25 | Segundo jabalí, 14 en comida | 4 casas y 14 aldeanos en comida |
| 7 | 8:35 | Segundo campamento, 9 leñadores | 5 casas, 2 campamentos y 9 leñadores |
| 8 | 9:55 | Campamento minero, 3 en oro | 1 campamento minero y 3 mineros de oro |
| 9 | 10:00 | Telar | Telar terminado |
| 10 | 10:05 | Clic en Edad Feudal | Edad Feudal en cola o investigándose |
| 11 | 12:15 | 6 granjas | 6 granjas terminadas |
| 12 | 13:10 | Mercado y Herrería | Edad Feudal, 1 mercado y 1 herrería |
| 13 | 13:10 | 28 aldeanos | 28 aldeanos |
| 14 | 13:15 | Clic en Castillos | Castillos en cola o investigándose |
| 15 | 13:50 | Hacha de doble filo y Collera | Las dos en cola, investigándose o terminadas |
| 16 | 15:55 | Edad de los Castillos | Edad de los Castillos |

**Tiempos de referencia:** suponen un centro urbano que nunca para (un aldeano cada 25 s, Telar 25 s, Feudal 130 s, Castillos 160 s), más unos segundos de camino. Coinciden con la nota más alta de AgeOfNotes (Feudal a las 10:05, Castillos a las 13:10), así que son exigentes. Se ajustan en el JSON.

### Scouts 21

La fuente es [build_orders/scouts_21.json](../content/guias/build_orders/scouts_21.json). Clic en Feudal con 21 de población (20 aldeanos y el explorador), establo al llegar y exploradores sin parar. Su meta (el hito que resume la partida en el historial) son los **6 exploradores**, no Castillos.

| # | Ref. | Título en el panel | Se marca hecho cuando |
|---|---|---|---|
| 1 | 0:35 | 2 casas | 2 casas terminadas |
| 2 | 1:20 | 6 pastores | 6 pastores |
| 3 | 3:10 | Campamento y 4 leñadores | 1 campamento maderero y 4 leñadores |
| 4 | 3:30 | Primer jabalí | 1 cazador o más |
| 5 | 5:15 | Casa, molino y 4 en bayas | 3 casas, 1 molino y 4 recolectores |
| 6 | 6:00 | Segundo jabalí, 13 en comida | 4 casas y 13 aldeanos en comida |
| 7 | 7:20 | Cuartel y 6 leñadores | 1 cuartel terminado y 6 leñadores |
| 8 | 7:30 | Telar | Telar terminado |
| 9 | 7:35 | Clic en Edad Feudal | Edad Feudal en cola o investigándose |
| 10 | 9:45 | Edad Feudal | Edad Feudal alcanzada |
| 11 | 10:20 | Establo | 1 establo terminado |
| 12 | 11:20 | 3 exploradores | 3 exploradores vivos (cuenta el inicial) |
| 13 | 11:40 | 4 granjas y 24 aldeanos | 4 granjas y 24 aldeanos |
| 14 | 12:50 | 6 exploradores | 6 exploradores vivos |

**Tiempos de referencia:** calculados como en Fast Castle (un aldeano cada 25 s, Feudal 130 s, exploradores de 30 s en un solo establo) más unos segundos de camino. Son una primera estimación: conviene ajustarlos con tus partidas.

**Exploradores:** se cuentan las unidades de caballería de exploración (ID 448) vivas, incluida la inicial. Si pierdes el explorador inicial, hace falta uno más. Las civilizaciones que empiezan con águila (aztecas, mayas, incas) no pueden seguir esta guía.

## Cómo funciona

- **El mapa carga el script.** La primera línea de cada mapa es `#includeXS guia_fast_castle.xs`. El resto es una copia literal del mapa oficial (`Arabia.rms`, `Arena.rms`), que `build.py` lee del juego en cada construcción. Así el mapa se genera exactamente igual que el oficial.
- **El script se repite cada segundo** (una `rule` de XS) y, para cada jugador humano:
  1. Toma los recuentos que necesitan las condiciones (casas, leñadores…).
  2. Anota la hora del primer momento en que se cumple cada paso pendiente. Mira también los pasos siguientes, no solo el actual. Así, si haces algo antes de tiempo (por ejemplo, atraer el jabalí antes de tener los 4 leñadores), queda anotado y no te atascas.
  3. Avanza por los pasos ya cumplidos, en orden.
  4. Rehace el texto del panel y solo lo vuelve a mostrar si ha cambiado.
- **Si te saltas un paso,** la guía espera en él mientras los siguientes se van anotando. Cuando lo completas, se marcan todos de golpe. Si llegas a Castillos con pasos sin hacer, la guía se cierra igual y esos pasos salen como `[-] … sin hacer`.
- **Cómo cuenta:** el aldeano cambia de tipo de unidad según su tarea (pastor 590/592, leñador 123/218, cazador 122/216…). `xsGetPlayerUnitIds` devuelve las unidades de cada tipo. Un edificio cuenta como terminado si sus puntos de construcción llegan a su tiempo de construcción o si tiene la vida al máximo; así los cimientos no cuentan.
- **Multijugador:** cada jugador humano tiene su propio progreso y el panel sale solo en su pantalla. La IA se ignora.

## Archivos

| Archivo | Qué es |
|---|---|
| `content/guias/build_orders/*.json` | Las build orders, como datos. |
| `content/mapas/mapas.json` | El catálogo de mapas: mapa oficial de base, nombre, tipo, descripción (español e inglés) y guías recomendadas. |
| `apps/desktop/dashboard.py` | El panel de AoE2C (sus cinco páginas). |
| `apps/desktop/instalador.py` | Activa la guía (copia su script como `aoe2c_guia.xs`), instala, quita y exporta mapas, abre el juego y el inicio con Windows. |
| `apps/desktop/config.py` | Preferencias compartidas por el panel y el overlay (`config.json`). |
| `apps/desktop/textos.py` | Textos del panel y los menús en español e inglés. |
| `apps/desktop/pruebas/test_panel.py` | Pruebas de Scouts, el lector, el instalador, las preferencias, los textos y el panel (`py apps/desktop/pruebas/test_panel.py`). |
| `apps/desktop/pruebas/test_arranque.py` | Arranca el programa entero sin pantalla: animación, panel, segunda copia y Cerrar AoE2C. |
| `content/guias/xs/utiles.xs` | Funciones de apoyo: contar unidades y edificios, estado de tecnologías, formato de tiempos. |
| `content/guias/xs/motor.xs` | El motor: estado por jugador, avance de pasos, panel y aviso de casas. |
| `content/guias/pruebas/prueba_panel.xs` | Maqueta del panel con datos inventados, para probar cambios de diseño (`--pruebas`). |
| `content/guias/build.py` | Valida los JSON, genera el XS, los mapas y los manifiestos del overlay, comprueba el XS y lo instala. |
| `apps/desktop/aoe2c.py` | El programa único (el futuro AoE2Coaching.exe). Con `--inicio` (inicio con Windows) espera en la bandeja sin abrir el panel. |
| `apps/desktop/rutas.py` | Encuentra el juego (bibliotecas de Steam) y la carpeta del perfil (pregunta si hay varias con uso), y dónde van los datos y los logs. |
| `apps/desktop/overlay.py` | El overlay: ventana, diseño, bandeja del sistema, `--demo` y `--captura`. |
| `apps/desktop/lector.py` | Busca y lee el `.xsdat` que escribe el juego. |
| `apps/desktop/historial.py` | Registra cada partida (pasos e hitos) y calcula mejores marcas, medias y puntos débiles. |
| `apps/desktop/historial_ui.py` | La ventana del historial. |
| `apps/desktop/estilo.py` | Colores y fuentes comunes del overlay y del historial. |
| `%APPDATA%\AoE2Coaching\historial.json` | Las partidas guardadas (se crea al jugar la primera). |
| `apps/desktop/pruebas/test_historial.py` | Pruebas del historial: simula partidas segundo a segundo, sin abrir ventanas (`py apps/desktop/pruebas/test_historial.py`). |
| `build/guias/*.json` | Manifiestos generados (`build/` no se sube a git): textos de cada guía y orden de los datos del `.xsdat`. |
| `apps/desktop/Iniciar overlay.bat` | Abre AoE2C (`aoe2c.py`) sin ventana de consola. |
| `apps/desktop/Cerrar overlay.bat` | Cierra el overlay sin usar el menú (por si no está visible). |
| `%APPDATA%\AoE2Coaching\config.json` | Preferencias del panel y del overlay, y las carpetas elegidas a mano (perfil, juego). |
| `%APPDATA%\AoE2Coaching\logs\aoe2c.log` | Log de AoE2C (carpetas encontradas y errores no capturados). |
| `build/mods/guia-apertura-castillos/resources/_common/xs/guia_fast_castle.xs` | Script final en un solo archivo: utilidades, funciones generadas de los pasos y motor. |
| `build/mods/guia-apertura-castillos/resources/_common/random-map-scripts/*.rms` | Los mapas. |

El script final va en un solo archivo porque el juego no reparte a los demás jugadores los `.xs` incluidos desde otro `.xs`.

## Cómo reconstruir e instalar

```bash
py content/guias/build.py --install
```

El script:

1. Lee todas las build orders de `content/guias/build_orders/` y comprueba nombres, condiciones, tiempos y textos.
2. Genera un `.xs` por build order y una copia de cada mapa de su lista que lo carga. Cada mapa lleva su imagen para la sala: un `.png` con el mismo nombre que el `.rms`, hecho con la imagen del mapa oficial (`wpfg\resources\mapicons\rm_<mapa>.png`) y una banda "AoE2 Coaching" encima.
3. Convierte las tildes de todos los textos en `chr(byte)` con sus bytes UTF-8, para que el archivo final sea ASCII puro.
4. Pasa un control del XS generado (ver "Lo que aprendimos de XS").
5. Con `--install`, copia el mod a `mods\local\guia-apertura-castillos` y cada `.xs` a `resources\_common\xs` del perfil. Sustituye los archivos uno a uno, sin borrar la carpeta, así que funciona con el juego abierto. Un mapa nuevo no sale en la lista hasta reiniciar el juego.

Opciones: `--ascii` escribe los textos sin tildes. `--pruebas` añade el mapa "Arena Prueba 4 panel" con la maqueta del panel.

## Cómo probarlo en el juego

1. Abre el juego. En **Mods**, comprueba que **"AoE2 Coaching"** esté activado. Si el juego ya estaba abierto al instalarlo, reinícialo.
2. Crea una partida para un jugador contra la IA y, en la sala, cambia:
   - **Modo de juego:** Mapa aleatorio (no "Escenario personalizado", que carga escenarios del editor).
   - **Estilo de mapa:** Personalizado (no Estándar).
   - **Ubicación:** [AoE2C] Arena o [AoE2C] Arabia.

   La sala recuerda el último mapa, así que hay que cambiarlo a mano. En los mapas oficiales (estilo Estándar) la guía no aparece.
3. Elige una civilización con un inicio normal (por ejemplo, francos o britanos).
4. Comprueba:
   - Que al empezar no sale ningún cuadro de error y aparece el panel con el paso 1 y los 3 siguientes.
   - Que el progreso se actualiza (Casas 0/2 → 1/2 → 2/2) y que el paso avanza solo, con sonido.
   - Que los pasos hechos muestran su hora y el desfase.
   - El aviso de casas: deja la población a 1 o 2 del límite sin construir casa.
   - Que al llegar a Castillos aparece "¡Guía completada!".
5. Si algo falla, la repetición dice qué mapa se jugó y qué scripts se cargaron:

   ```bash
   py tools/inspect_record.py
   ```

## Cómo añadir otra build order

Copia `build_orders/scouts_21.json` con otro nombre, cambia `id`, `archivo_xs` y los pasos, y reconstruye. Cada JSON genera su propio script y su manifiesto, y sale como una tarjeta más en la página Guías del panel.

Claves generales: `id` (minúsculas y `_`), `nombre`, `descripcion` y `descripcion_en`, `nivel` (`facil`, `media` o `dificil`), `mapas_recomendados` (ids de `mapas.json`), `hitos` (de `clic_feudal`, `feudal`, `clic_castillos`, `castillos` y `meta` = último paso), `series` (1 o 2 hitos para el gráfico de evolución), `hito_principal`, `titulo_final` e `icono_final` (la tarjeta al completar la guía), `archivo_xs` (sin espacios), `margen_segundos` (margen para "a tiempo"), `aviso_casas`, `overlay` y `panel_juego` (true/false, al menos uno activado), `pasos_hechos_visibles` y `pasos_siguientes_visibles` (0 a 5) y `mensaje_final`.

**Mapas:** se añaden en `mapas.json`. Cada uno lleva `id`, `base` (un `.rms` oficial de `gamedata_x2`), `archivo` (el nombre con que sale en el juego), `nombre`, `tipo` y `descripcion` (con `es` y `en`), `guias` (ids de guías recomendadas) y, si la imagen oficial no se llama `rm_<base>.png`, `imagen`. Los mapas que ya cargan su propio script XS no sirven de base; `build.py` lo avisa.

Cada paso lleva:

- `titulo`: la línea corta de la lista (hasta 32 caracteres, para que no se parta).
- `texto`: la instrucción completa, que solo se ve en el paso actual.
- `icono`, `referencia` (`m:ss`) y `condiciones`.

El paso se cumple cuando se cumplen todas sus condiciones:

| Condición | Ejemplo | Valores |
|---|---|---|
| Edificios terminados | `{"edificio": "casa", "min": 2}` | `casa`, `molino`, `campamento_maderero`, `campamento_minero`, `granja`, `mercado`, `herreria`, `cuartel`, `centro_urbano` |
| Aldeanos en una tarea | `{"aldeanos": "lenadores", "min": 4}` | `pastores`, `lenadores`, `cazadores`, `recolectores`, `mineros_oro`, `mineros_piedra`, `granjeros`, `pescadores`, `constructores`, `comida` (suma de las tareas de comida), `todos` |
| Unidades militares vivas | `{"unidades": "exploradores", "min": 3}` | `exploradores` (cuenta la inicial) |
| Tecnología | `{"tecnologia": "telar", "estado": "terminada"}` | `telar`, `edad_feudal`, `edad_castillos`, `edad_imperial`, `hacha_doble_filo`, `sierra_de_arco`, `collera`, `arado_pesado`, `carretilla`, `mineria_aurifera`; estado `iniciada` (en cola, investigándose o terminada) o `terminada` |
| Edad alcanzada | `{"edad": "feudal"}` | `feudal`, `castillos`, `imperial` |

Iconos: `casa`, `molino`, `campamento_maderero`, `campamento_minero`, `granja`, `mercado`, `herreria`, `cuartel`, `centro_urbano`, `castillo`, `aldeano`, `oveja`, `jabali`, `establo`, `explorador`. Edificios: también `establo`.

**Textos:** se pueden escribir con tildes, ñ, `·`, `«»` y `¡¿`, es decir, cualquier carácter latino. Los demás símbolos (✓, ▶, —, •) salen como "?" en el panel y `build.py` los rechaza. Tampoco se admiten `%`, comillas, barras invertidas ni `<` (el juego lo toma como etiqueta de color).

Para añadir edificios, tareas o tecnologías, se amplían las tablas del principio de `build.py`. Los IDs salen de `resources\_common\dat\CivTechTrees\*.json` y `random_map.def`.

## Límites

- **Solo en partidas con estos mapas**, contra la IA o en una sala personalizada. **No funciona en clasificatorias**, porque ahí solo se juega con mapas oficiales. Para clasificatorias existen overlays externos como RTS_Overlay, que se avanzan a mano o por tiempo.
- **El panel tapa parte de la vista** arriba en el centro: unas 10 líneas de unos 50 caracteres. El juego no deja moverlo; se puede acortar con `pasos_hechos_visibles` y `pasos_siguientes_visibles`.
- **Un solo color por panel:** el juego solo acepta la etiqueta de color al principio del texto, así que el panel no puede colorear cada línea.
- **Civilizaciones con un inicio distinto** (más aldeanos, pastos en lugar de granjas, casas que no hacen falta…) pueden seguir la guía, pero los números y los tiempos no les cuadran. Los pastos no cuentan como granjas.
- **Multijugador:** el juego reparte a los demás jugadores el `.xs` que el anfitrión tiene en la carpeta `xs` de su perfil. Sin probar.

## Lo que aprendimos de XS

Útil para próximos mods con XS. Varias cosas salieron de pruebas en el juego con mapas de diagnóstico (`pruebas/`):

- **El compilador XS solo acepta ASCII.** Un solo carácter no ASCII en cualquier parte del archivo (también dentro de un texto o de un comentario) hace que el juego muestre al empezar un cuadro de error con una línea por byte, ilegible, y que desactive el script. Así fallaba la v1 ("Guía", "leñadores"…).
- **Las tildes se construyen al ejecutar:** `chr(195) + chr(173)` da "í" (los bytes UTF-8). `chr(237)` también se ve bien, pero solo por un modo de compatibilidad. `build.py` usa siempre los bytes UTF-8.
- **Solo caracteres latinos:** á, ñ, ·, «, », ¡, ¿ se ven bien. ✓ y ▶ salen como "?".
- **Panel de instrucciones** (`xsDisplayInstructions`):
  - Admite varias líneas con `\n` y crece hacia abajo.
  - Mide unos 50 caracteres de ancho y parte las líneas largas.
  - Solo admite una etiqueta de color al principio del texto: `<RED>` funciona; `<YELLOW>` dejó un ">" suelto; las etiquetas a mitad de texto salen escritas tal cual.
  - `cPanelBottom` aparece justo debajo del panel de arriba, no al pie de la pantalla.
- **Funciones probadas en un mapa aleatorio:** `xsGetPlayerUnitIds`, `xsArrayGetSize`, `xsGetTechState`, `xsGetObjectAttribute`, `xsGetPlayerType`, `xsGetUnitBuildPoints`, `xsGetUnitHitpoints`, `xsUnsyncGetLocalPlayerId`, `xsSendChat`, `xsChatData`, `xsDisplayInstructions` y `chr`. Las `rule` se ejecutan durante la partida. `xsGetObjectCount` no se ha probado, porque la v1 falló antes por las tildes; la v2 no la usa.
- **Escribir archivos para un programa externo** (probado en una partida): `xsCreateFile(false)` compila en un mapa aleatorio y sobrescribe el archivo cada vez. El juego lo guarda en `…\<id de Steam>\profile\<nombre del mapa>.xsdat`. `xsWriteInt` escribe enteros de 32 bits. Es la única forma de sacar datos de la partida.
- **Lección del overlay:** buscar ese archivo recorriendo carpetas grandes (como Documentos, con más de un millón de archivos) tardaba 18 s y congelaba el programa: se veía casi transparente porque la animación no avanzaba, y Windows lo marcaba como "no responde". Ahora solo mira la carpeta `profile`.
- **El script del mapa tiene su propio runtime,** con `Constants.xs` y sin `Effects.xs`.
- **Dónde va el `.xs`.** Un mapa dentro de un mod no encuentra el `.xs` del propio mod (error `0354: failed to open file`, bug abierto desde 2021). Sí lo encuentra en `resources\_common\xs` del perfil, que es donde lo copia `--install`. El mod también lleva su copia, por si el juego lo arregla.
- **Firmas de las funciones.** El ejecutable del juego trae el prototipo de cada función XS como texto, y es más fiable que las guías. Por ejemplo, `bool xsDisplayInstructions(string msg, int time, int sourcePlayer, int iconObjectId, int panelPosition, bool playerColorForText, bool playSound, string soundFilename, int playerId)`. También trae la lista de mensajes de error del compilador y las palabras reservadas.
- **Atributos de población.** `cAttributePopulationCap` (4) es el espacio **libre** de población, no el límite. `cAttributeUnitLimit` (32) es un bonus (los godos tienen +10). La capacidad visible es población + espacio libre.
- **Trampas del lenguaje** (todas las comprueba `build.py`):
  - `return` siempre con paréntesis.
  - No existen `!`, el menos unario ni `+=`.
  - El tipo de una operación lo decide el primer operando, así que las concatenaciones empiezan por una cadena.
  - Los parámetros llevan valor por defecto.
  - Una función solo puede llamar a funciones definidas antes.
  - Las cadenas globales no conservan su valor.
  - Nada de comillas simples ni `%` en los textos.
  - Por prudencia, los literales se trocean a 70 caracteres y las funciones guardan el resultado en una variable antes del `return`.
- **Las repeticiones sirven para depurar.** La cabecera de un `.aoe2record` guarda la configuración de la sala y el código de todos los `.xs` cargados. `tools/inspect_record.py` lo resume, y también lista las funciones compiladas de cada script. Ojo: cuando la compilación falla, solo queda guardada la primera función, así que esa lista no indica dónde está el error.
- **Los mapas cambian de bioma.** Arabia (v3.3) y Arena pueden salir con otro ganado, como gansos. Los aldeanos que lo pastorean siguen siendo pastores (590/592), pero los textos no deben decir solo "ovejas".
- **Referencia de la comunidad:** la UGC Guide (ugc.aoe2.rocks); sus fuentes en markdown están en el repositorio `Divy1211/AoE2DE_UGC_Guide`.

## Pendiente

- **Probar el historial en una partida:** que se abra al salir, que la pestaña del menú no tape ningún botón del juego y que los tiempos de Feudal y Castillos cuadren con la pantalla de puntuación.
- **Civilización en el historial:** el `.xsdat` no la incluye; se podría añadir al script XS o sacarla de la repetición.

- **Probar en una partida** que al salir de la partida se reinicia y que la animación de plegado va fluida.
- **Pendiente de la v2:** que los edificios en construcción no cuentan como terminados y el aviso de casas.
- **Aviso de centro urbano parado:** el recurso 80 del jugador ("Queued Units") permitiría detectar un centro urbano sin aldeanos en cola. Es la métrica más útil en un Fast Castle.
- **Probar el panel y Scouts en una partida:** que el panel se abra tras la animación, que "Usar esta guía" cambie la guía en la siguiente partida y que los tiempos de referencia de Scouts sean razonables.
- **Más build orders:** Arqueros, Drush FC, Hombres de armas → Arqueros y Águilas (ya salen como "Próximamente" en el panel).
- **Traducir la tarjeta de la partida y el historial** al inglés (ahora solo el panel y los menús).
- **Indicaciones visuales** (opción B): XS tiene `xsFlashUnit`, `xsSetUnitCaption` y `xsSetViewPosition`, que podrían señalar unidades o edificios en el mapa.
