# Página oficial de AoE2C (plan 8)

- **Estado:** primera versión hecha el 2026-11-07 en `apps/web`. Probada en local (escritorio y móvil). **Falta conectarla a Vercel** y apuntar el subdominio.
- **Plan:** [03-plan-compartir-aoe2c.md](03-plan-compartir-aoe2c.md) (decisión 6 y paso 8).

## Qué es

Una sola página (Astro, estática) con scroll suave y animaciones ligadas al scroll, en español e inglés:

| Sección | Qué tiene |
|---|---|
| **Portada** | Paisaje en cinco capas (cielo, montes, castillo, pueblo y primer plano) con parallax al bajar y con el ratón, brasas y botón de descarga. |
| **Cómo funciona** | La tarjeta del overlay rehecha en HTML. La sección queda fija y, al bajar, la tarjeta avanza por los 9 primeros pasos **reales** de Fast Castle 27+2 (reloj, ritmo, barras, "A continuación" y aviso de casas). |
| **Empezar** | Cuatro pasos con una línea que se dibuja al bajar. |
| **El panel** | El panel rehecho en HTML: la ventana se endereza al entrar y el gráfico de "tiempo hasta Castillos" se dibuja. Debajo, cuatro ventajas. |
| **Guías** | Una tarjeta por build order (nivel, pasos, meta, mapas y la lista de pasos desplegable), con inclinación al pasar el ratón. |
| **Mapas** | Galería horizontal que avanza con el scroll vertical (en móvil, deslizable). Las vistas aéreas se generan en la web. |
| **MODs** | Las fichas de `content/mods/*/catalogo.json`, con ovejas animadas y su marcador. |
| **Descargar** | Botón de la última versión, pasos de instalación y el aviso de SmartScreen animado ("Más información" → "Ejecutar de todas formas"). |
| **Preguntas** | Gratis, aviso de Windows, Xbox, partidas clasificatorias, cómo lee la partida, datos y desinstalar. |

Con "reducir movimiento" activado en el sistema no hay scroll suave ni animaciones: todo queda visible y quieto. Sin JavaScript se ve toda la página en español.

## Decisiones

- **Sin arte del juego.** Las capturas llevarían sprites e imágenes de mapas de Microsoft. En su lugar, la tarjeta y el panel están rehechos en HTML (con los colores de `apps/desktop/estilo.py`) y el paisaje, los iconos, las vistas de los mapas y las ovejas son SVG propios.
- **Contenido leído de `content/` al armar**, no del `catalogo.json` publicado: son las mismas fuentes que usa `content/catalogo.py`, así la web coincide con el panel aunque todavía no haya una publicación `contenido-*`. La versión de la app sale de `apps/desktop/version.py`. Ver [contenido.ts](../apps/web/src/lib/contenido.ts).
- **Descarga.** El botón apunta a `releases/latest/download/AoE2Coaching-Setup-<versión>.exe`. Al abrir la página, el navegador consulta la API de GitHub y lo cambia por la última `desktop-v*` publicada (y su versión). Si aún no hay ninguna, lleva a la página de versiones.
- **Idioma.** Cada texto está escrito en los dos idiomas (`<T es en>`) y el CSS muestra el de `<html lang>`. La primera vez sale del navegador; el botón ES/EN lo guarda en `localStorage`.
- **Librerías:** Astro 7.4.1 (la última que funciona con Node 22.22), GSAP 3 con ScrollTrigger, Lenis para el scroll suave y las fuentes Cinzel e Inter servidas desde la propia web (sin Google Fonts).

## Uso

```bash
npm --prefix apps/web install
```

```bash
npm --prefix apps/web run dev
```

```bash
npm --prefix apps/web run build
```

El resultado queda en `apps/web/dist`. [web.yml](../.github/workflows/web.yml) comprueba que se arma en cada cambio de `apps/web`, `content` o `version.py`.

## Publicar en Vercel (una vez)

1. En Vercel, **Add New → Project** e importar `Zoen-DEV/aoe2-coaching`.
2. **Root Directory:** `apps/web`. Vercel reconoce Astro solo (build `npm run build`, salida `dist`). Dejar marcada la opción de incluir los archivos de fuera de la carpeta raíz: la web lee `content/` y `apps/desktop/version.py`.
3. **Settings → Domains:** añadir `aoec.zoen.dev` y crear en el DNS de `zoen.dev` el registro CNAME que indique Vercel.

Después, cada push a `main` publica la web, y cada pull request tiene su vista previa.

## Pendiente

- Imagen para compartir en redes (`og:image`), ahora es el logo.
