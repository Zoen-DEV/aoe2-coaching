# AoE2 Coaching (AoE2C)

Guías de apertura paso a paso encima de Age of Empires II: Definitive Edition, historial de partidas y un panel para elegir guía, ver el historial e instalar mapas y mods.

- **Estado:** en preparación para la primera versión pública. Plan: [docs/03-plan-compartir-aoe2c.md](docs/03-plan-compartir-aoe2c.md).
- **Diseño de la guía y del panel:** [docs/02-guia-apertura-castillos.md](docs/02-guia-apertura-castillos.md)
- **Mod de las ovejas:** [docs/01-icono-ovejas.md](docs/01-icono-ovejas.md)
- **Catálogo de contenido** (guías, mapas y mods que instala el panel): [docs/04-catalogo-contenido.md](docs/04-catalogo-contenido.md)
- **Página oficial:** <https://aoec.zoen.dev> (código en `apps/web`, ver [docs/05-pagina-oficial.md](docs/05-pagina-oficial.md))
- **Discord** (dudas y reportes de errores): <https://discord.gg/yR6e99cbh>

## Estructura

```
apps/
  desktop/        app de Windows (Python + PySide6): overlay, panel e instalador de contenido
    empaquetado/  armado con PyInstaller e instalador de Inno Setup
    pruebas/      pruebas de la app (y de la validación de las guías)
  web/            página oficial (Astro, GSAP y Lenis): una sola página en español e inglés
  api/            backend en Node - cuando lleguen las cuentas
content/
  catalogo.py     arma el catálogo (paquetes + catalogo.json) en build/catalogo
  guias/          build.py + build orders (.json) -> script .xs y manifiesto del overlay
                  tierlist.json (ajustes de la tierlist) y tecnologias.json (datos del juego, de tecnologias.py)
  mapas/          mapas.json: recetas de los mapas [AoE2C]
  mods/
    icono-ovejas/ build.py + info.json -> sprites .sld con el icono; catalogo.json: su ficha
tools/            herramientas de sprites (.sld) y de repeticiones (.aoe2record)
.github/
  workflows/      desktop.yml (pruebas y publicación de la app), contenido.yml (catálogo) y web.yml (armado de la web)
  scripts/        juego falso y descarga de mods publicados, para GitHub Actions
docs/
build/            todo lo generado (no se sube a git)
```

Lo generado va a `build/`: los mapas `.rms` son copias de mapas oficiales y los `.sld` derivan de sprites del juego, así que no se publican en el repositorio. Para armarlos hace falta el juego instalado.

## Entorno

- Python 3.14 (en Windows se ejecuta con `py`), Git y AoE2 DE en Steam. Para la web, Node 22.22 o posterior.
- Dependencias:

```bash
py -m pip install -r requirements.txt
```

El juego se busca en las bibliotecas de Steam y el perfil en `%USERPROFILE%\Games\Age of Empires 2 DE\<id>` (si hay varios con partidas, el panel pregunta cuál usar). Los scripts de `content/` y `tools/` usan las mismas carpetas. Ver [apps/desktop/rutas.py](apps/desktop/rutas.py).

## Uso

Armar las guías, los mapas y el mod de AoE2C (sin `--install` no toca el juego):

```bash
py content/guias/build.py
```

Volver a sacar del juego las tecnologías y civilizaciones de la tierlist (con una civilización nueva o al añadir una tecnología a su catálogo; el resultado, `content/guias/tecnologias.json`, se sube a git):

```bash
py content/guias/tecnologias.py
```

Armar el catálogo con lo construido (las guías y el mod de las ovejas). Desde el código, el panel lo usa en vez del publicado en GitHub; `AOE2C_CATALOGO` elige otro (ruta o URL):

```bash
py content/catalogo.py
```

Abrir la app (overlay y panel). Sus preferencias, el historial, los logs y el contenido descargado quedan en `%APPDATA%\AoE2Coaching\`:

```bash
py apps/desktop/aoe2c.py
```

Ver el panel Match Info (jugadores y elo en las partidas clasificatorias) con una partida inventada: pasa cada 4 s por «buscando datos», cargado y error, se puede arrastrar (se pega al borde más cercano) y se cierra con Esc o clic derecho. `equipos` o `sin_rating` en vez de `1v1`; `--izquierda` para verlo en el borde izquierdo:

```bash
py apps/desktop/match_ui.py --demo 1v1
```

La app entera con una partida clasificatoria simulada (una repetición inventada en una carpeta temporal y elo de ejemplo, sin red): el panel aparece, a los 2 s carga el elo, `Ctrl+Alt+M` lo oculta y lo muestra, y a los 30 s la partida acaba y el demo se cierra. No guarda nada ni toca el inicio con Windows, y funciona aunque AoE2C esté abierto:

```bash
py apps/desktop/overlay.py --demo-match 1v1
```

Correr las pruebas (necesitan el contenido armado en `build/`):

```bash
py apps/desktop/pruebas/test_panel.py
```

```bash
py apps/desktop/pruebas/test_historial.py
```

```bash
py apps/desktop/pruebas/test_partida.py
```

```bash
py apps/desktop/pruebas/test_match_ui.py
```

```bash
py apps/desktop/pruebas/test_arranque.py
```

```bash
py apps/desktop/pruebas/test_rutas.py
```

```bash
py apps/desktop/pruebas/test_catalogo.py
```

```bash
py apps/desktop/pruebas/test_soporte.py
```

```bash
py apps/desktop/pruebas/test_empaquetado.py
```

Exportar el logo (SVG, PNG e `.ico`) a `build/marca`:

```bash
py apps/desktop/logo.py
```

Armar la app para instalar: la carpeta de PyInstaller en `build/desktop/dist/AoE2Coaching` y el instalador en `build/instalador/AoE2Coaching-Setup-<versión>.exe` (necesita Inno Setup 6.7 o posterior: `winget install JRSoftware.InnoSetup`; `--sin-instalador` arma solo la app). Ver [apps/desktop/empaquetado](apps/desktop/empaquetado):

```bash
py apps/desktop/empaquetado/empaquetar.py
```

Armar el mod de las ovejas:

```bash
py content/mods/icono-ovejas/build.py
```

## Publicar

Con etiquetas de git: `desktop-v<versión>` publica el instalador y `contenido-<fecha>` publica el catálogo. GitHub Actions corre las pruebas antes y no publica nada si alguna falla. Los pasos, y cómo publicar un mod nuevo, en el plan: [Publicación automática](docs/03-plan-compartir-aoe2c.md#publicación-automática-paso-7).

## Herramientas

| Script | Para qué |
|---|---|
| `tools/sld.py` | Leer y escribir sprites `.sld` de AoE2 DE (todas las capas, incluida la máscara de 1 bit). |
| `tools/inspect_sld.py` | Resumir la estructura de un `.sld` y comprobar que la lectura y la escritura dan el mismo archivo. |
| `tools/render_sld.py` | Convertir frames de un `.sld` a PNG, con simulación de color de jugador. |
| `tools/inspect_record.py` | Ver en una repetición (`.aoe2record`) qué mapa se jugó y qué scripts XS se cargaron. Sin argumentos, usa la más reciente. |
| `tools/banderas.py` | Generar `apps/desktop/banderas_datos.py` (las banderas del panel Match Info) desde el paquete de npm de flag-icons descomprimido. |

## Referencias del juego

- **Juego (Steam):** `C:\Program Files (x86)\Steam\steamapps\common\AoE2DE`
- **Mods locales (perfil):** `%USERPROFILE%\Games\Age of Empires 2 DE\<id>\mods\local\`
- **Scripts XS del perfil:** `...\<id>\resources\_common\xs\`. Los mapas buscan aquí los `.xs` de `#includeXS`; dentro de un mod no los encuentran.
- **Mapas oficiales (`.rms`):** `resources\_common\drs\gamedata_x2`
- **Sprites:** `resources\_common\drs\graphics`
- **Herramientas incluidas en el juego** (`Tools_Builds`): `AdvancedGenieEditor3.exe` y `Sprites\DESpriteTool.exe`.

## Licencia

[GNU AGPL v3](LICENSE). Puedes usar, modificar y compartir el código; si distribuyes una versión modificada (o la ofreces como servicio en red), tienes que publicar su código con la misma licencia.
