"""Diseños del icono, en pixel art al estilo de los indicadores del juego.

Cada diseño devuelve (rgba, pc):
- rgba: HxWx4 uint8, alfa 0 o 255.
- pc: HxW uint8, 255 donde el juego pinta el color del jugador.

Estilo común (inspirado en el "!" de aldeano ocioso):
- contorno marrón muy oscuro de 1 px,
- marco dorado de 1 px con luz arriba a la izquierda y sombra abajo a la derecha,
- interior en color de jugador. El juego mezcla el color del jugador con el gris
  del píxel: gris medio (~128) = color puro, más claro = hacia blanco, más oscuro =
  hacia negro. Por eso el interior usa grises medios con sombreado.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

OUTLINE = (30, 20, 10)
GOLD_LIGHT = (255, 232, 150)
GOLD_MID = (222, 172, 70)
GOLD_DARK = (128, 84, 30)
SHINE = (255, 250, 230)
SS = 8  # supermuestreo para rasterizar formas


def _raster(w: int, h: int, draw_fn) -> np.ndarray:
    """Dibuja con PIL a SS veces el tamaño y devuelve la máscara 1x (cobertura >= 50%)."""
    img = Image.new("L", (w * SS, h * SS), 0)
    draw_fn(ImageDraw.Draw(img), SS)
    a = np.asarray(img, dtype=np.float64) / 255.0
    return a.reshape(h, SS, w, SS).mean(axis=(1, 3)) >= 0.5


def _erode(m: np.ndarray) -> np.ndarray:
    """Erosión en cruz (vecinos arriba, abajo, izquierda, derecha)."""
    p = np.pad(m, 1)
    return m & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]


def _lerp(a, b, t):
    t = min(max(t, 0.0), 1.0)
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _gold(t: float):
    """t=0 luz, t=1 sombra."""
    return _lerp(GOLD_LIGHT, GOLD_MID, t * 2) if t < 0.5 else _lerp(GOLD_MID, GOLD_DARK, (t - 0.5) * 2)


def _diag(x, y, w, h) -> float:
    """0 arriba a la izquierda, 1 abajo a la derecha."""
    return (x / max(w - 1, 1) + y / max(h - 1, 1)) / 2


def _compose(shape: np.ndarray, field_gray, shine: set | None = None, rim: bool = True):
    """Contorno + marco dorado + interior en color de jugador.

    field_gray(x, y, w, h) -> gris del interior (0-255).
    """
    h, w = shape.shape
    inner1 = _erode(shape)
    inner2 = _erode(inner1) if rim else inner1
    rgba = np.zeros((h, w, 4), np.uint8)
    pc = np.zeros((h, w), np.uint8)
    for y in range(h):
        for x in range(w):
            if not shape[y, x]:
                continue
            if not inner1[y, x]:
                c = OUTLINE
            elif not inner2[y, x]:
                c = _gold(_diag(x, y, w, h))
            elif shine and (x, y) in shine:
                c = SHINE
            else:
                g = int(field_gray(x, y, w, h))
                c = (g, g, g)
                pc[y, x] = 255
            rgba[y, x] = (*c, 255)
    return rgba, pc


# ---------------------------------------------------------------------------
# Diseños
# ---------------------------------------------------------------------------


def escudo():
    """Escudo de heráldica (heater): marco dorado y campo en color de jugador."""
    w, h = 13, 15

    def draw(d, s):
        pts = [(0.5, 0.5), (12.5, 0.5), (12.5, 6.5), (11.6, 9.6), (9.4, 12.3), (6.5, 14.6), (3.6, 12.3), (1.4, 9.6), (0.5, 6.5)]
        d.polygon([(x * s, y * s) for x, y in pts], fill=255)

    shape = _raster(w, h, draw)

    def gray(x, y, w, h):
        # Luz arriba a la izquierda; mitad derecha algo más oscura (relieve central).
        g = 165 - 85 * _diag(x, y, w, h)
        return g - (12 if x > w // 2 else 0)

    return _compose(shape, gray, shine={(3, 3), (4, 3), (3, 4)})


def estandarte():
    """Estandarte colgando de una barra dorada, con cola en V."""
    w, h = 13, 17
    rgba = np.zeros((h, w, 4), np.uint8)
    pc = np.zeros((h, w), np.uint8)

    def cloth_draw(d, s):
        pts = [(1.5, 2.5), (11.5, 2.5), (11.5, 16.5), (6.5, 12.6), (1.5, 16.5)]
        d.polygon([(x * s, y * s) for x, y in pts], fill=255)

    cloth = _raster(w, h, cloth_draw)
    folds = [0, 14, 22, 14, 0, -10, -18, -10, 0, 12, 18, 10, 0]

    def gray(x, y, w, h):
        return 150 + folds[x] - 70 * (y / (h - 1))

    c_rgba, c_pc = _compose(cloth, gray, rim=False)
    m = c_rgba[..., 3] > 0
    rgba[m], pc[m] = c_rgba[m], c_pc[m]
    # Barra dorada con remates.
    for x in range(w):
        for y in (1, 2):
            if x in (0, w - 1) and y == 2:
                continue
            rgba[y, x] = (*_gold(0.15 if y == 1 else 0.6), 255)
            pc[y, x] = 0
    for x in range(w):
        rgba[0, x] = (*OUTLINE, 255)
    for x in (0, w - 1):
        rgba[1, x] = (*OUTLINE, 255)
        rgba[2, x] = (*OUTLINE, 255)
    rgba[3, 1:12] = (*OUTLINE, 255)  # sombra de la barra sobre la tela
    pc[3, 1:12] = 0
    return rgba, pc


def gema():
    """Gema tallada en forma de rombo alargado hacia abajo, con engaste dorado."""
    w, h = 13, 17

    def draw(d, s):
        pts = [(6.5, 0.3), (12.6, 6.0), (6.5, 16.7), (0.4, 6.0)]
        d.polygon([(x * s, y * s) for x, y in pts], fill=255)

    shape = _raster(w, h, draw)
    cx, cy = 6, 6

    def gray(x, y, w, h):
        # Cuatro caras: arriba-izq clara, arriba-der media, abajo-izq media-oscura, abajo-der oscura.
        top, left = y <= cy, x <= cx
        if top and left:
            return 175
        if top:
            return 135
        if left:
            return 110
        return 72

    return _compose(shape, gray, shine={(5, 3), (4, 4), (5, 4)})


def flecha():
    """Flecha gruesa apuntando hacia abajo."""
    w, h = 13, 15

    def draw(d, s):
        pts = [(3.5, 0.5), (9.5, 0.5), (9.5, 6.5), (12.6, 6.5), (6.5, 14.7), (0.4, 6.5), (3.5, 6.5)]
        d.polygon([(x * s, y * s) for x, y in pts], fill=255)

    shape = _raster(w, h, draw)

    def gray(x, y, w, h):
        return 165 - 90 * _diag(x, y, w, h)

    return _compose(shape, gray, shine={(5, 3), (5, 4)})


def pin():
    """El pin de la v2 (para comparar)."""
    w, h = 15, 19
    s = SS
    cx = w / 2 * s
    r = (w / 2 - 0.5) * s
    cy = r + 0.5 * s

    def draw(d, _s):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
        d.polygon([(cx - r * 0.72, cy + r * 0.69), (cx + r * 0.72, cy + r * 0.69), (cx, (h - 0.5) * s)], fill=255)

    shape = _raster(w, h, draw)
    inner = _erode(shape)
    rgba = np.zeros((h, w, 4), np.uint8)
    pc = np.zeros((h, w), np.uint8)
    for y in range(h):
        g = round(235 + (150 - 235) * y / (h - 1))
        for x in range(w):
            if not shape[y, x]:
                continue
            if not inner[y, x]:
                rgba[y, x] = (25, 25, 25, 255)
            elif (x - 7) ** 2 + (y - 7) ** 2 <= 4:
                rgba[y, x] = (245, 245, 245, 255)
            else:
                rgba[y, x] = (g, g, g, 255)
                pc[y, x] = 255
    return rgba, pc


DESIGNS = {
    "escudo": escudo,
    "estandarte": estandarte,
    "gema": gema,
    "flecha": flecha,
    "pin": pin,
}
