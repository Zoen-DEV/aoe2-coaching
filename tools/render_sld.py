"""Renderiza frames de un SLD a PNG para revisarlos.

Uso: py tools/render_sld.py archivo.sld salida.png [--frames 0,30,60] [--scale 3]

Cada frame se muestra en varias columnas: imagen principal, máscara de color de
jugador y la oveja coloreada con varios colores de jugador simulados.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import sld  # noqa: E402

# Colores base de jugador aproximados y "gaia" (animal sin dueño; en el juego se ve blanco).
PLAYER_COLORS = {
    "azul": (45, 45, 245),
    "rojo": (210, 40, 40),
    "verde": (30, 180, 30),
    "amarillo": (215, 215, 30),
    "gris": (150, 150, 150),
    "gaia": (235, 235, 235),
}
BG = (96, 128, 72)  # parecido a la hierba


def decode_frames(path, limit: int | None = None):
    """Devuelve una lista de dicts por frame con imágenes en coordenadas de lienzo.
    Con `limit` solo decodifica los primeros frames."""
    s = sld.read(path)
    prev: dict = {}
    out = []
    for f in s.frames[:limit]:
        canvas_main = np.zeros((f.height, f.width, 4), dtype=np.uint8)
        canvas_pc = np.zeros((f.height, f.width), dtype=np.uint8)
        canvas_shadow = np.zeros((f.height, f.width), dtype=np.uint8)
        for kind in ("main", "shadow", "playercolor"):
            layer = f.layers.get(kind)
            if layer is None:
                prev.pop(kind, None)
                continue
            grid = sld.block_grid(layer, prev.get(kind))
            prev[kind] = (layer, grid)
            img = sld.decode_layer(layer, grid)
            h, w = img.shape[:2]
            target = {"main": canvas_main, "shadow": canvas_shadow, "playercolor": canvas_pc}[kind]
            target[layer.y1 : layer.y1 + h, layer.x1 : layer.x1 + w] = img
        out.append(
            {
                "index": f.frame_index,
                "hotspot": (f.hotspot_x, f.hotspot_y),
                "main": canvas_main,
                "pc": canvas_pc,
                "shadow": canvas_shadow,
            }
        )
    return out


def tint(rgb: np.ndarray, base) -> np.ndarray:
    """Cómo mezcla el juego el color de jugador (aproximación ajustada con una captura real):
    gris medio = color puro del jugador; más claro va hacia blanco; más oscuro hacia negro."""
    base = np.asarray(base, dtype=np.float64)
    g = rgb.astype(np.float64).mean(axis=-1, keepdims=True) / 255.0
    return np.where(g <= 0.5, base * (g / 0.5), base + (255.0 - base) * ((g - 0.5) / 0.5))


def composite(fr, color) -> np.ndarray:
    """Aproximación del render del juego: sombra, color base y color de jugador
    donde la máscara lo indica."""
    h, w = fr["pc"].shape
    img = np.ones((h, w, 3), dtype=np.float64) * np.array(BG, dtype=np.float64)
    shadow = fr["shadow"].astype(np.float64) / 255.0
    img *= 1.0 - 0.5 * shadow[..., None]
    rgb = fr["main"][..., :3].astype(np.float64)
    alpha = (fr["main"][..., 3] > 0)[..., None]
    pc = fr["pc"].astype(np.float64)[..., None] / 255.0
    colored = rgb * (1 - pc) + np.clip(tint(rgb, color), 0, 255) * pc
    img = np.where(alpha, colored, img)
    return np.clip(img, 0, 255).astype(np.uint8)


def crop_box(frames, margin=8):
    ys, xs = [], []
    for fr in frames:
        m = (fr["main"][..., 3] > 0) | (fr["shadow"] > 0)
        yy, xx = np.nonzero(m)
        if len(yy):
            ys += [yy.min(), yy.max()]
            xs += [xx.min(), xx.max()]
    return max(min(ys) - margin, 0), max(ys) + margin, max(min(xs) - margin, 0), max(xs) + margin


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sld")
    ap.add_argument("out")
    ap.add_argument("--frames", default="0")
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--colors", default="azul,rojo,gris")
    args = ap.parse_args()

    frames = decode_frames(args.sld)
    wanted = [frames[int(i)] for i in args.frames.split(",")]
    y0, y1, x0, x1 = crop_box(wanted)
    colors = args.colors.split(",")
    tiles_rows = []
    for fr in wanted:
        tiles = []
        main = fr["main"]
        checker = np.indices(main.shape[:2]).sum(axis=0) // 4 % 2
        base = np.where(checker[..., None] == 1, 200, 160).astype(np.uint8).repeat(3, axis=2)
        a = (main[..., 3] > 0)[..., None]
        tiles.append(np.where(a, main[..., :3], base))
        pcv = np.stack([fr["pc"]] * 3, axis=2)
        tiles.append(pcv)
        for c in colors:
            tiles.append(composite(fr, PLAYER_COLORS[c]))
        tiles = [t[y0:y1, x0:x1] for t in tiles]
        sep = np.full((tiles[0].shape[0], 2, 3), 255, dtype=np.uint8)
        row = tiles[0]
        for t in tiles[1:]:
            row = np.concatenate([row, sep, t], axis=1)
        tiles_rows.append(row)
    sheet = np.concatenate(
        [np.concatenate([r, np.full((2, r.shape[1], 3), 255, dtype=np.uint8)], axis=0) for r in tiles_rows], axis=0
    )
    img = Image.fromarray(sheet).resize((sheet.shape[1] * args.scale, sheet.shape[0] * args.scale), Image.NEAREST)
    img.save(args.out)
    print(f"guardado {args.out} ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
