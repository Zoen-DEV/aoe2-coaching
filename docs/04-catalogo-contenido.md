# Catálogo de contenido (plan 3)

- **Estado:** hecho el 2026-11-07, con pruebas de código ([test_catalogo.py](../apps/desktop/pruebas/test_catalogo.py)). **Falta probar en el juego** cómo trata `mod-status.json` las líneas que añade AoE2C (ver "Por comprobar en el juego").
- **Plan:** paso 3 de [03-plan-compartir-aoe2c.md](03-plan-compartir-aoe2c.md) (decisiones 5, 10 y 14).
- **Código:** [apps/desktop/catalogo.py](../apps/desktop/catalogo.py) (formato y descargas), [apps/desktop/mapas.py](../apps/desktop/mapas.py) (armado de mapas), [apps/desktop/instalador.py](../apps/desktop/instalador.py) (instalar en el juego) y [content/catalogo.py](../content/catalogo.py) (generador).

## Qué es

Una lista publicada en GitHub Releases (`catalogo.json`) con todo lo que el panel puede instalar: guías, mapas y mods. Así una guía nueva no obliga a sacar otra versión del `.exe`.

- **Guías y mods** llegan en un paquete `.zip`. El panel lo descarga y comprueba su tamaño y su SHA-256 antes de usarlo; si no coincide, lo borra y no instala nada.
- **Mapas** no traen archivos: son una receta (mapa oficial, nombre, imagen). AoE2C los arma con el `.rms` oficial del juego del usuario, así que no se publican archivos de Microsoft.
- Cada elemento lleva su **versión** y la **versión mínima de la app** (`app_minima`). Si la app es más vieja, el botón dice "Necesita actualizar AoE2C".
- La última lista descargada se guarda en `%APPDATA%\AoE2Coaching\contenido\catalogo.json`: sin conexión, el panel usa esa.

## Formato (versión 1)

```json
{
  "formato": 1,
  "generado": "2026-11-07T18:00:00Z",
  "elementos": [
    {
      "tipo": "guia",
      "id": "fast_castle",
      "version": "1.0.0",
      "app_minima": "1.0.0",
      "nombre": {"es": "Fast Castle 27+2", "en": "Fast Castle 27+2"},
      "descripcion": {"es": "…", "en": "…"},
      "paquete": {"archivo": "guia-fast_castle-1.0.0.zip", "sha256": "e1a3…", "tamano": 8682},
      "datos": {"archivo_xs": "guia_fast_castle.xs", "nivel": "media", "mapas_recomendados": ["arena", "arabia"]}
    }
  ]
}
```

| Campo | Qué es |
|---|---|
| `formato` | Versión del formato. Una app que lee un formato mayor que el suyo pide actualizarse. |
| `tipo` | `guia`, `mapa` o `mod`. Una app vieja ignora los tipos que no conoce. |
| `id` | Minúsculas, números, `_` y `-`. Único por tipo. |
| `version`, `app_minima` | Números separados por puntos (`1.2.0`). Se comparan como números. |
| `nombre`, `descripcion` | Textos en español e inglés (los dos obligatorios). |
| `paquete` | Solo guías y mods. `archivo` es relativo al `catalogo.json` (o una URL completa). |

`datos` según el tipo:

| Tipo | `datos` | Paquete |
|---|---|---|
| `guia` | `archivo_xs`, `nivel`, `mapas_recomendados` | Manifiesto del overlay (`guia_<id>.json`) y script (`guia_<id>.xs`). |
| `mapa` | `base` (el `.rms` oficial), `archivo` (`[AoE2C] ….rms`), `imagen` (opcional: la imagen oficial si no sigue la regla `rm_<base>.png`), `tipo` (texto en los dos idiomas), `guias` | Ninguno. |
| `mod` | `carpeta` (nombre en `mods\local`), `titulo` (el `Title` de su `info.json`) | La carpeta del mod tal como va en `mods\local`, con su `info.json`. |

## De dónde sale

`py content/catalogo.py` lee lo ya construido en `build/` y escribe `build/catalogo/`:

| Elemento | Fuente | Su versión |
|---|---|---|
| Guías | `build/guias/*.json` y sus `.xs` (de `content/guias/build.py`) | `"version"` de la build order (`content/guias/build_orders/*.json`). La `app_minima` sale del formato del manifiesto (`APP_MINIMA_GUIA` en el generador). |
| Mapas | `content/mapas/mapas.json` | `"version"` de cada mapa (y `app_minima` opcional). |
| Mods | `build/mods/<id>/` (de `content/mods/<id>/build.py`) | `content/mods/<id>/catalogo.json`: versión, `app_minima`, título y textos. |

Los `.zip` tienen fechas y orden fijos: si no cambia el contenido, el hash no cambia. **Al cambiar una guía, un mapa o un mod hay que subir su versión**; si no, el panel no ofrece actualizarlo.

Publicarlo (subir los `.zip` y `catalogo.json` a una publicación con etiqueta `contenido-*`) es el paso 7 del plan. La app busca la publicación `contenido-*` más reciente con la API de GitHub.

### Desde el código

Al ejecutar `py apps/desktop/aoe2c.py`, el panel usa `build/catalogo/catalogo.json` si existe (después de `py content/catalogo.py`). La variable `AOE2C_CATALOGO` elige otro catálogo (ruta o URL).

## En la PC del usuario

| Qué | Dónde |
|---|---|
| Guías instaladas | `%APPDATA%\AoE2Coaching\contenido\guias\` (manifiesto + script). La guía activa se copia como `aoe2c_guia.xs` a la carpeta `xs` del perfil, como antes. |
| Versiones instaladas y activaciones pendientes | `%APPDATA%\AoE2Coaching\contenido\instalado.json` (los mods, por perfil). |
| Imágenes de los mapas para el panel | `%APPDATA%\AoE2Coaching\contenido\imagenes\` |
| Mapas | El mod local `guia-apertura-castillos` del perfil, como antes. |
| Mods | `mods\local\<carpeta>` del perfil. |

- **Mapas al día con el juego.** Un mapa instalado tiene que ser exactamente "cabecera + `.rms` oficial". Al abrir el panel y al llegar el catálogo, los que no coinciden (el juego actualizó el oficial, o cambió la receta) se vuelven a armar solos.
- **La primera guía** que se instala queda activa. Al actualizar la guía activa, su script se vuelve a copiar.
- Para instalar un mapa hace falta al menos una guía (todos cargan `aoe2c_guia.xs`).

## mod-status.json (decisión 10)

Es la lista de mods del juego (`<perfil>\mods\mod-status.json`), sin documentación oficial. Cada línea es así:

```json
{"CheckSum":"1520413741","Enabled":true,"LastUpdate":"0","Path":"local//icono-ovejas","Priority":10,"PublishID":0,"Title":"Icono sobre el ganado","WorkshopID":0}
```

Reglas de AoE2C:

- **Solo con el juego cerrado.** Si está abierto, la activación queda pendiente (en `instalado.json`) y el panel la aplica en cuanto se cierra, aunque sea en otra sesión de AoE2C. El panel lo muestra: "Se activará al cerrar el juego".
- **Copia antes de escribir:** `mod-status.json.aoe2c.bak`, junto al original.
- **Solo nuestras líneas** (`local//guia-apertura-castillos` y las de nuestros mods). Las demás quedan igual y en el mismo orden. Si nuestra línea existe, solo cambia `Enabled`; si no, se añade al final con la prioridad siguiente a la más alta.
- **Quitar un mod** borra su carpeta y su línea (también con el juego cerrado).
- **Si el archivo no se entiende**, no se toca, y el panel explica cómo activarlo a mano (Mods → Mods instalados).
- El panel muestra si el jugador desactivó el mod en el juego y ofrece **Activar**.

Los mods tampoco se actualizan ni se quitan con el juego abierto (tiene sus archivos cargados). Un mod nuevo sí se copia con el juego abierto; solo su activación espera.

### Por comprobar en el juego

- Una línea nueva lleva `"CheckSum":"0"`: no se sabe cómo calcula el juego ese valor. Hay que comprobar que lo recalcula y deja el mod activo.
- Si el perfil no tiene `mod-status.json`, AoE2C lo crea (`{"Mods":[…],"Unsub":[]}`). Hay que comprobar que el juego lo acepta y añade los demás mods.
- Si el juego registra solo los mods locales nuevos, y si los registra activos o desactivados.

## Pruebas

`py apps/desktop/pruebas/test_catalogo.py` usa un juego falso (con `.rms` oficiales inventados) y carpetas temporales ([apoyo.py](../apps/desktop/pruebas/apoyo.py)): no toca el juego, el perfil ni `%APPDATA%`. Cubre el formato, el hash (paquetes alterados o con bytes de más), los paquetes con rutas `../`, la copia sin conexión, guías, mapas (rearmado al cambiar el oficial), mods, las reglas de `mod-status.json` y las páginas Guías, Mapas y MODs (también con la descarga de verdad en segundo plano).
