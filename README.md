# AoE2 Coaching (AoE2C)

Guías de apertura paso a paso encima de Age of Empires II: Definitive Edition, historial de partidas y un panel para elegir guía, ver estadísticas e instalar mapas y mods.

- **Estado:** en preparación para la primera versión pública. Plan: [docs/03-plan-compartir-aoe2c.md](docs/03-plan-compartir-aoe2c.md).
- **Diseño de la guía y del panel:** [docs/02-guia-apertura-castillos.md](docs/02-guia-apertura-castillos.md)
- **Mod de las ovejas:** [docs/01-icono-ovejas.md](docs/01-icono-ovejas.md)

## Estructura

```
apps/
  desktop/        app de Windows (Python + PySide6): overlay, panel e instalador de contenido
    pruebas/      pruebas de la app (y de la validación de las guías)
  web/            página oficial (Astro) - plan 8
  api/            backend en Node - cuando lleguen las cuentas
content/
  guias/          build.py + build orders (.json) -> script .xs y manifiesto del overlay
  mapas/          mapas.json: recetas de los mapas [AoE2C]
  mods/
    icono-ovejas/ build.py + info.json -> sprites .sld con el icono
tools/            herramientas de sprites (.sld) y de repeticiones (.aoe2record)
docs/
build/            todo lo generado (no se sube a git)
```

Lo generado va a `build/`: los mapas `.rms` son copias de mapas oficiales y los `.sld` derivan de sprites del juego, así que no se publican en el repositorio. Para armarlos hace falta el juego instalado.

## Entorno

- Python 3.14 (en Windows se ejecuta con `py`), Git y AoE2 DE en Steam.
- Dependencias:

```bash
py -m pip install -r requirements.txt
```

Por ahora las rutas del juego y del perfil están fijas en el código (`C:\Program Files (x86)\Steam\...` y `C:\Users\User\Games\Age of Empires 2 DE\<id>`). Detectarlas solas es el plan 2.

## Uso

Armar las guías, los mapas y el mod de AoE2C (sin `--install` no toca el juego):

```bash
py content/guias/build.py
```

Abrir la app (overlay y panel):

```bash
py apps/desktop/overlay.py
```

Correr las pruebas (necesitan el contenido armado en `build/`):

```bash
py apps/desktop/pruebas/test_panel.py
```

```bash
py apps/desktop/pruebas/test_historial.py
```

```bash
py apps/desktop/pruebas/test_arranque.py
```

Armar el mod de las ovejas:

```bash
py content/mods/icono-ovejas/build.py
```

## Herramientas

| Script | Para qué |
|---|---|
| `tools/sld.py` | Leer y escribir sprites `.sld` de AoE2 DE (todas las capas, incluida la máscara de 1 bit). |
| `tools/inspect_sld.py` | Resumir la estructura de un `.sld` y comprobar que la lectura y la escritura dan el mismo archivo. |
| `tools/render_sld.py` | Convertir frames de un `.sld` a PNG, con simulación de color de jugador. |
| `tools/inspect_record.py` | Ver en una repetición (`.aoe2record`) qué mapa se jugó y qué scripts XS se cargaron. Sin argumentos, usa la más reciente. |

## Referencias del juego

- **Juego (Steam):** `C:\Program Files (x86)\Steam\steamapps\common\AoE2DE`
- **Mods locales (perfil):** `%USERPROFILE%\Games\Age of Empires 2 DE\<id>\mods\local\`
- **Scripts XS del perfil:** `...\<id>\resources\_common\xs\`. Los mapas buscan aquí los `.xs` de `#includeXS`; dentro de un mod no los encuentran.
- **Mapas oficiales (`.rms`):** `resources\_common\drs\gamedata_x2`
- **Sprites:** `resources\_common\drs\graphics`
- **Herramientas incluidas en el juego** (`Tools_Builds`): `AdvancedGenieEditor3.exe` y `Sprites\DESpriteTool.exe`.

## Licencia

Pendiente de decidir (GPL o AGPL); ver el plan.
