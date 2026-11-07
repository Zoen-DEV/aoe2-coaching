"""Compara los diseños del icono sobre animales reales del juego.

Uso: py content/mods/icono-ovejas/compare.py [diseño1,diseño2,...]

Genera preview/comparacion.png: una fila por diseño y una columna por animal y
color de jugador. Simula cómo mezcla el juego el color de jugador (aproximado).
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))
import icons  # noqa: E402
import sld  # noqa: E402
from render_sld import decode_frames, tint  # noqa: E402

GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common")
GRAPHICS = GAME / "drs" / "graphics"
PALETTES = GAME / "palettes"
SCALE = 3


def player_base(name: str) -> np.ndarray:
    tokens = (PALETTES / f"playercolor_{name}.pal").read_text().split()
    return np.array([int(t) for t in tokens[3:6]], dtype=np.float64)


# (animal, archivo, frame, color). "gaia" = animal sin dueño (en la captura sale blanco).
COLUMNS = [
    ("Oveja", "a_herd_sheep_walkA_x1.sld", 0, "yellow"),
    ("Ganso", "a_herd_goose_walkA_x1.sld", 60, "blue"),
    ("Vaca", "a_herd_cow_brown_walkA_x1.sld", 0, "red"),
    ("Cerdo", "a_herd_pig_walkA_x1.sld", 240, "green"),
    ("Cabra", "a_herd_goat_walkA_x1.sld", 0, "purple"),
    ("Oveja sin dueño", "a_herd_sheep_idleA_x1.sld", 0, "gaia"),
]
GAIA = np.array([235.0, 235.0, 235.0])
COLOR_NAMES = {"yellow": "amarillo", "blue": "azul", "red": "rojo", "green": "verde", "purple": "morado", "gaia": "sin dueño"}


def font(size: int):
    try:
        return ImageFont.truetype("segoeui.ttf", size)
    except OSError:
        return ImageFont.load_default()


def render_tile(file: str, frame_idx: int, color: str, icon, bg: np.ndarray) -> np.ndarray:
    s = sld.read(GRAPHICS / file)
    bottom = min(f.layers["main"].y1 - f.hotspot_y for f in s.frames)
    fr = decode_frames(GRAPHICS / file, limit=frame_idx + 1)[frame_idx]
    hx, hy = fr["hotspot"]
    base = GAIA if color == "gaia" else player_base(color)

    th, tw = bg.shape[:2]
    out = bg.astype(np.float64).copy()
    ox, oy = tw // 2 - hx, th - 22 - hy  # posición del animal dentro de la casilla

    def paste(rgb, alpha, pcm, x0, y0):
        h, w = alpha.shape
        for y in range(h):
            for x in range(w):
                ty, tx = y0 + y, x0 + x
                if 0 <= ty < th and 0 <= tx < tw and alpha[y, x]:
                    c = rgb[y, x].astype(np.float64)
                    p = pcm[y, x] / 255.0
                    out[ty, tx] = c * (1 - p) + tint(c, base) * p

    # Sombra del animal.
    sh = fr["shadow"].astype(np.float64) / 255.0
    for y, x in zip(*np.nonzero(sh)):
        ty, tx = oy + y, ox + x
        if 0 <= ty < th and 0 <= tx < tw:
            out[ty, tx] *= 1 - 0.45 * sh[y, x]
    paste(fr["main"][..., :3], fr["main"][..., 3] > 0, fr["pc"], ox, oy)
    rgba, pc = icon
    ih, iw = pc.shape
    paste(rgba[..., :3], rgba[..., 3] > 0, pc, ox + hx - iw // 2, oy + hy + bottom - ih)
    return np.clip(out, 0, 255).astype(np.uint8)


def main() -> None:
    names = sys.argv[1].split(",") if len(sys.argv) > 1 else list(icons.DESIGNS)
    bg = np.asarray(Image.open(HERE / "preview" / "fondo_hierba.png").convert("RGB"))
    bg = bg[:96, :84]
    label_w = 90
    rows = []
    for name in names:
        icon = icons.DESIGNS[name]()
        tiles = [render_tile(f, i, c, icon, bg) for _, f, i, c in COLUMNS]
        row = np.concatenate([np.pad(t, ((0, 0), (0, 2), (0, 0)), constant_values=255) for t in tiles], axis=1)
        rows.append((name, row))
    th = rows[0][1].shape[0]
    tw = rows[0][1].shape[1]
    sheet = Image.new("RGB", (label_w + tw * SCALE, 30 + len(rows) * (th * SCALE + 6)), (245, 240, 228))
    d = ImageDraw.Draw(sheet)
    for i, (label, _, _, color) in enumerate(COLUMNS):
        text = label if color == "gaia" else f"{label} ({COLOR_NAMES[color]})"
        d.text((label_w + i * (bg.shape[1] + 2) * SCALE + 6, 6), text, fill=(40, 30, 20), font=font(15))
    for r, (name, row) in enumerate(rows):
        y = 30 + r * (th * SCALE + 6)
        img = Image.fromarray(row).resize((tw * SCALE, th * SCALE), Image.NEAREST)
        sheet.paste(img, (label_w, y))
        d.text((8, y + th * SCALE // 2 - 12), f"{chr(65 + r)}. {name.capitalize()}", fill=(40, 30, 20), font=font(18))
    out = HERE / "preview" / "comparacion.png"
    sheet.save(out)
    print(f"guardado {out}")


if __name__ == "__main__":
    main()
