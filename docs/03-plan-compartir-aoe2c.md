# Plan: compartir AoE2 Coaching (primera versión pública)

- **Estado:** plan acordado el 2026-11-07. Pasos 1 a 8 hechos el 2026-11-07 (monorepo en GitHub; juego, perfil y datos sin rutas fijas; catálogo de contenido: [04-catalogo-contenido.md](04-catalogo-contenido.md); todo AoE2C en inglés; repeticiones en el historial y soporte; empaquetado y publicación automática: ver "Empaquetado" y "Publicación automática" abajo; página oficial: [05-pagina-oficial.md](05-pagina-oficial.md), falta conectarla a Vercel). La primera ejecución en GitHub (push del plan 7) falló en `test_panel.py` y `test_catalogo.py`: Windows está en inglés en GitHub y las pruebas esperaban el panel en español. Corregido el 2026-11-07 fijando el español dentro de las pruebas (`pruebas/apoyo.py` y `test_arranque.py`); todas pasan en una copia limpia simulando Windows en inglés. Falta comprobarlo en GitHub al subir. Falta poner la invitación del Discord en `apps/desktop/soporte.py` cuando se cree el servidor (paso 9).
- **Objetivo:** que cualquier jugador pueda descargar AoE2C desde su página oficial, instalarlo como un programa normal (al estilo de Blitz) y, desde el panel, instalar guías, mapas y mods.
- **Mod actual:** [02-guia-apertura-castillos.md](02-guia-apertura-castillos.md)

## Decisiones

| # | Tema | Decisión | Por qué |
|---|---|---|---|
| 1 | Cuentas | **Sin cuentas en la primera versión.** El historial y las estadísticas quedan en la PC del usuario. Las cuentas (signup, login, logout) y el backend en Node llegan con la web. | Sin servidor ni base de datos, sale antes y su mantenimiento es gratis. Una cuenta solo aporta algo cuando hay web o comparación entre jugadores. |
| 2 | Versión del juego | **Solo Steam**, pero la app busca sola la carpeta del perfil (sin un ID fijo) para poder sumar Xbox / Microsoft Store después. | No hay forma de probar la versión de Xbox. |
| 3 | Repositorio | **Monorepo público** `aoe2-coaching` en GitHub. Licencia: GPL como opción (y AGPL para el backend); queda por cerrar. | Las descargas desde GitHub Releases son gratis, el código a la vista da confianza para instalar un .exe sin firma, y los mapas y scripts no se pueden ocultar igual. |
| 4 | Instalación | **Instalador con Inno Setup** en `%LOCALAPPDATA%\AoE2Coaching` (sin permisos de administrador), acceso en el menú Inicio, desinstalador y **actualización con un clic**: al abrirse, la app consulta GitHub Releases. | Es lo que espera un usuario de un programa estilo Blitz, y el inicio con Windows necesita una ruta fija. |
| 5 | Contenido | **El panel descarga guías, mapas y mods** desde un catálogo en GitHub Releases. Cada elemento lleva su versión, su hash y la **versión mínima de la app** que necesita. El instalador no trae contenido. | Así una guía nueva no obliga a sacar otra versión del .exe, y una app vieja no instala contenido que no entiende ("Necesita actualizar la app"). |
| 6 | Página oficial | **Astro** en `apps/web`, alojada en **Vercel**, en un subdominio de `zoen.dev` (sugerido: `aoe2c.zoen.dev`). | La primera versión solo necesita una página estática, y Astro puede crecer después a una web con login. El plan gratis de Vercel es para uso no comercial: si algún día hay funciones de pago, hay que pasar a Pro. |
| 7 | Firma del .exe | **Sin firma en la primera versión.** La web explica el aviso de SmartScreen con capturas, y cada versión se envía a Microsoft para que la analice. | Firmar cuesta dinero o exige verificar identidad. Se reconsidera cuando haya usuarios. |
| 8 | Errores y uso | **Sin Sentry.** El panel tiene un acceso al **Discord de AoE2 Coaching** (con un canal de errores) y un botón **"Copiar datos para soporte"** (versión de la app, de Windows y últimos errores del log). El uso se mide con las **descargas de GitHub**. Las estadísticas de uso esperan al backend. | Sin servidor no hay otra forma de enterarse de los errores, y con los datos copiados los reportes sirven de algo. |
| 9 | Repos y mods | El monorepo incluye **AoE2C y el mod de las ovejas**. El panel suma una pestaña **"MODs"** para instalar nuestros mods. `aoe-mods` queda para experimentos sueltos. | Los mods se publican desde el mismo catálogo que las guías y los mapas. |
| 10 | Activar mods | **La app los activa sola** en `mods\mod-status.json`, **solo con el juego cerrado** (si está abierto, espera a que se cierre), guarda una copia del archivo antes y solo toca nuestras líneas, respetando el orden de los otros mods. Si falla, explica cómo activarlo a mano. | El archivo no está documentado y el juego lo puede pisar si está abierto. |
| 11 | Idiomas | **Todo en español e inglés**: panel, pasos de las guías, tarjeta del overlay y web. La primera vez el idioma sale del de Windows. | La mayoría de los jugadores usa el juego en inglés. |
| 12 | Publicación | **GitHub Actions** con dos procesos: la etiqueta `desktop-v*` corre las pruebas, arma la app con PyInstaller en modo carpeta, arma el instalador y lo publica; la etiqueta `contenido-*` construye guías y mods, arma el catálogo con los hashes y lo publica. | Arma todo en una máquina limpia y no publica nada si una prueba falla. |
| 13 | Desinstalar | Dos casillas: ☑ **quitar las guías, mapas y mods de AoE2C del juego** (y sus líneas de `mod-status.json`), ☐ **borrar el historial y la configuración**. Para tocar archivos del juego, el juego tiene que estar cerrado. | Deja el juego como estaba sin que pierda el historial quien solo reinstala. |
| 14 | Mapas | **La app arma los mapas [AoE2C] en la PC del usuario**: lee el `.rms` oficial de su instalación y le agrega `#includeXS aoe2c_guia.xs` (lo mismo que hoy hace `build.py`). El catálogo solo trae la "receta" (mapa base, nombre e imagen). Si el juego actualiza el mapa oficial, la app lo vuelve a armar. | No se publican archivos de Microsoft y los mapas siempre coinciden con la versión actual del juego. |
| 15 | Repeticiones | **Primera versión: vincular** cada partida del historial con su `.aoe2record` ("Ver repetición", "Mostrar en carpeta"). **Segunda versión: leerlas** con `mgz` (civilizaciones, rival, resultado, APM, orden real de construcción). | Leerlas por completo depende de una librería externa que puede fallar después de cada parche. |

## Respuestas a preguntas de fondo

- **Backend en Node con una app en Python:** no hay problema. Se comunican por HTTP y JSON (en Python con `httpx` o `requests`). El token de sesión irá en el Administrador de credenciales de Windows (`keyring`), y la app tiene que seguir funcionando sin conexión.
- **Base de datos:** no hace falta en la primera versión. Se elige cuando llegue el backend.
- **¿Hay que estar conectado a Steam?** No. El mod no habla con Steam; solo el botón "Abrir AoE2" usa `steam://`.
- **¿El juego guarda las partidas?** Sí. Cada partida deja un `.aoe2record` en `savegame` del perfil, también las de los mapas [AoE2C] (la repetición guarda incluso el script de la guía). Las partidas online quedan además en los servidores de Microsoft, pero no hay una API pública oficial, y las partidas contra la IA no se suben.

## Estructura del monorepo

```
aoe2-coaching/
  apps/
    desktop/      app de Windows (Python + PySide6): overlay, panel, instalador de contenido
    web/          página oficial (Astro)
    api/          backend en Node (cuando lleguen las cuentas)
  content/
    guias/        cada guía: build order (.json) -> script .xs + datos del overlay
    mapas/        recetas de los mapas [AoE2C] (mapa base, nombre, imagen, guías recomendadas)
    mods/
      icono-ovejas/
  tools/          herramientas de sprites (sld.py, render_sld.py, inspect_sld.py) e inspect_record.py
  docs/
  .github/workflows/   desktop.yml y contenido.yml
```

## Orden de trabajo

1. **Crear el monorepo.** Repo público `aoe2-coaching`, pasar el código de `mods/guia-apertura-castillos`, `mods/icono-ovejas` y `tools/` a la estructura de arriba, y comprobar que las pruebas siguen pasando.
2. **Quitar lo que solo funciona en esta PC.**
   - Encontrar la carpeta del perfil (`%USERPROFILE%\Games\Age of Empires 2 DE\<id>`) y, si hay más de una, preguntar cuál usar. Encontrar el juego con las bibliotecas de Steam (`libraryfolders.vdf`).
   - Pasar `config.json`, `historial.json` y los logs a `%APPDATA%\AoE2Coaching\`, migrando los archivos actuales.
   - Un solo programa que abre el overlay o el panel según cómo se lance. El inicio con Windows apunta al .exe.
3. **Catálogo de contenido.**
   - Formato del catálogo (tipo, id, versión, hash, versión mínima de la app, textos en los dos idiomas).
   - Descarga con verificación del hash, en las páginas Guías, Mapas y la nueva **MODs**.
   - Armado local de los mapas a partir del `.rms` oficial, y nuevo armado cuando el oficial cambia.
   - Activación de mods en `mod-status.json` con las reglas de la decisión 10.
4. **Inglés completo.** Pasos e instrucciones de las guías, tarjeta del overlay e idioma inicial según Windows.
5. **Historial y soporte.** Vincular las repeticiones, log de errores, botón "Copiar datos para soporte" y acceso al Discord.
6. **Empaquetado.** PyInstaller en modo carpeta, instalador de Inno Setup con las casillas de desinstalación, y aviso y actualización desde GitHub Releases.
7. **Publicación automática.** Los dos procesos de GitHub Actions. Ver "Publicación automática" abajo.
8. **Página oficial.** Hecho: [05-pagina-oficial.md](05-pagina-oficial.md). Astro en Vercel con el subdominio: qué es, capturas, botón de descarga de la última versión, lista de guías y mapas leída del catálogo, y preguntas frecuentes (aviso de Windows, Xbox).
9. **Lanzamiento.** Crear el servidor de Discord, cerrar la licencia, enviar el instalador a Microsoft, publicar `desktop-v1.0.0` y `contenido-…`, y probarlo en una PC limpia.

## Empaquetado (paso 6)

- **Armar:** `py apps/desktop/empaquetado/empaquetar.py` exporta el logo (`build/marca/aoe2c.ico`), arma la app con PyInstaller en modo carpeta (`build/desktop/dist/AoE2Coaching`) y compila [aoe2c.iss](../apps/desktop/empaquetado/aoe2c.iss) con Inno Setup 6.7 o posterior (`build/instalador/AoE2Coaching-Setup-<versión>.exe`). La versión sale de `apps/desktop/version.py`.
- **Instalador:** `%LOCALAPPDATA%\AoE2Coaching`, sin administrador, en español o inglés, acceso en el menú Inicio y, si se elige, en el escritorio. Antes de copiar cierra la copia abierta (`AoE2Coaching.exe --salir`) y borra `_internal` para no mezclar bibliotecas de dos versiones.
- **Desinstalar:** una ventana con las dos casillas de la decisión 13. Lo hace la propia app (`AoE2Coaching.exe --desinstalar [--juego] [--datos]`, en [desinstalar.py](../apps/desktop/desinstalar.py)): en todos los perfiles quita `aoe2c_guia.xs` y los `guia_*.xs`, el mod de los mapas, los mods instalados desde el panel y sus líneas de `mod-status.json`; siempre quita el inicio con Windows. Con el juego abierto devuelve 2 y el desinstalador pide cerrarlo (Reintentar) o sigue sin tocar el juego (Cancelar).
- **Actualizar:** [actualizacion.py](../apps/desktop/actualizacion.py). Al abrir el panel por primera vez, la app instalada busca en GitHub Releases la publicación `desktop-v<versión>` más nueva con su `AoE2Coaching-Setup-<versión>.exe`. Si hay una, el panel muestra "Actualizar a vX" en la barra lateral (y en Ajustes, "Versión de AoE2C"). Al pulsarlo, descarga el instalador, comprueba su tamaño y el SHA-256 que da GitHub, lo abre con `/SILENT` y se cierra; el instalador pone la versión nueva y vuelve a abrir AoE2C. En plena partida no actualiza. Desde el código no busca (`AOE2C_ACTUALIZAR=1` lo fuerza).
- **Pruebas:** [test_empaquetado.py](../apps/desktop/pruebas/test_empaquetado.py) (elegir y descargar la versión, el panel, la desinstalación con un perfil inventado y `--salir`).

## Publicación automática (paso 7)

Dos procesos de GitHub Actions en `windows-latest`, con Python 3.14. En GitHub no está el juego: [juego_falso.py](../.github/scripts/juego_falso.py) crea uno con los `.rms` inventados de las pruebas y `AOE2C_JUEGO` le dice a `build.py` que lo use. Los mapas armados así no se publican (el catálogo solo lleva las guías y las recetas de los mapas), y los paquetes de las guías salen idénticos a los armados con el juego de verdad.

- **[desktop.yml](../.github/workflows/desktop.yml).** En cada push a `main` y en cada pull request: arma las guías y el catálogo (sin mods) y corre todas las pruebas de `apps/desktop/pruebas`. Con la etiqueta `desktop-v<versión>`, si las pruebas pasan: comprueba que la etiqueta coincide con `apps/desktop/version.py`, instala la última versión de Inno Setup, corre `empaquetar.py` y publica `AoE2Coaching-Setup-<versión>.exe` en la publicación de esa etiqueta.
- **[contenido.yml](../.github/workflows/contenido.yml).** Con la etiqueta `contenido-*` (por ejemplo `contenido-2026-11-07`): arma las guías, corre `test_panel.py` y `test_catalogo.py`, arma el catálogo y publica `catalogo.json` con los `.zip`. La publicación no queda como "Latest" en GitHub, para que esa marca siga en la última versión de la app. A mano (`workflow_dispatch`) arma el catálogo y lo deja como artefacto, sin publicar.
- **Mods.** Se arman con los sprites del juego, así que no se pueden armar en GitHub. [mods_publicados.py](../.github/scripts/mods_publicados.py) baja los `mod-*.zip` de la última publicación `contenido-*` y de la publicación **`mods-fuente`**, y `content/catalogo.py --mods-previos` los reutiliza sin cambiar sus bytes (su hash no cambia y el panel no ofrece una actualización falsa). Si falta el `.zip` de una versión, el proceso falla y explica qué hacer.

### Publicar

1. **App:** subir `VERSION` en `apps/desktop/version.py`, hacer commit y subir la etiqueta:

   ```bash
   git tag desktop-v1.0.0
   git push origin main desktop-v1.0.0
   ```

2. **Contenido:** subir la `version` de lo que cambió (build order, `mapas.json` o la ficha del mod) y subir una etiqueta `contenido-<fecha>`. Si la misma fecha ya existe, añadir `-2`.

   ```bash
   git tag contenido-2026-11-07
   git push origin main contenido-2026-11-07
   ```

3. **Mod nuevo o versión nueva de un mod** (antes del paso 2): `py content/mods/<id>/build.py`, después `py content/catalogo.py`, y subir `build/catalogo/mod-<id>-<versión>.zip` a la publicación `mods-fuente` en GitHub (Releases → `mods-fuente` → Edit → adjuntar). La publicación `mods-fuente` se crea una vez, marcada como pre-release; la app la ignora. **Para la primera publicación de contenido hace falta subir así `mod-icono-ovejas-1.0.0.zip`.**

## Para versiones siguientes

- Leer las repeticiones completas con `mgz` (segunda versión).
- Cuentas, backend en Node y base de datos, junto con la web de estadísticas.
- Estadísticas de uso y, si hace falta, Sentry.
- Soporte para Xbox / Microsoft Store.
- Firma del .exe.

## Pendiente de decidir

- Licencia: GPL o AGPL (o una para la app y otra para el backend).
- Subdominio definitivo (`aoe2c.zoen.dev` o `aoec.zoen.dev`).
- Base de datos del backend, cuando llegue.
