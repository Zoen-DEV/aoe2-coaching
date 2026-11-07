"""Construye el mod "Icono sobre el ganado".

Lee los sprites originales de todos los animales de pastoreo del juego (ovejas,
cerdos, cabras, llamas, pavos, vacas...), les añade un icono flotante encima
(en color de jugador) y escribe los sprites nuevos en build/mods/icono-ovejas/ (raíz del monorepo).

Uso: py content/mods/icono-ovejas/build.py [--install] [--only oveja,cerdo...]

--install  copia el mod a la carpeta de mods locales del juego.
--only     construye solo algunos animales (nombre interno: sheep, pig, goat...).
"""

import copy
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
RAIZ = HERE.parents[2]  # raíz del monorepo
sys.path.insert(0, str(RAIZ / "tools"))
sys.path.insert(0, str(RAIZ / "apps" / "desktop"))  # rutas.py: busca el juego y el perfil
import rutas  # noqa: E402
sys.path.insert(0, str(HERE))
import icons  # noqa: E402
import sld  # noqa: E402
from render_sld import PLAYER_COLORS, composite, decode_frames  # noqa: E402

_JUEGO, _PERFIL = rutas.para_scripts()
GAME_GRAPHICS = _JUEGO / "resources" / "_common" / "drs" / "graphics"
MOD_DIR = RAIZ / "build" / "mods" / "icono-ovejas"
OUT_DIR = MOD_DIR / "resources" / "_common" / "drs" / "graphics"
PREVIEW_DIR = HERE / "preview"
LOCAL_MODS = _PERFIL / "mods" / "local"
INSTALL_NAME = "icono-ovejas"

# Animaciones del animal vivo (quieto, caminando, corriendo). La muerte y el
# cadáver no llevan icono.
ANIMATION_RE = re.compile(r"^a_herd_(?P<animal>.+?)_(?P<anim>idle[AB]?|walk[A]?|run[A]?)_x1\.sld$")

# --- Ajustes del icono -------------------------------------------------------
# Diseño: uno de icons.DESIGNS (escudo, estandarte, gema, flecha, pin).
# Para comparar diseños: py mods/icono-ovejas/compare.py
ICON_DESIGN = "gema"
GAP = 0  # píxeles extra entre el recuadro del animal y la punta del icono

ICON_RGBA, ICON_PC = icons.DESIGNS[ICON_DESIGN]()
ICON_H, ICON_W = ICON_PC.shape


class IconBlocks:
    """El icono comprimido en bloques de 4x4. Como el animal puede tener el punto de
    apoyo en cualquier píxel, el icono puede caer desplazado (0-3 px) dentro de la
    rejilla; se comprime una vez por cada desplazamiento y se reutiliza."""

    def __init__(self, rgba: np.ndarray, pc: np.ndarray):
        self.rgba, self.pc = rgba, pc
        self.cache: dict = {}

    def get(self, ox: int, oy: int):
        """Devuelve (bloques de ancho, bloques de alto, {(bx, by): (bc1, bc4, bits de máscara)})."""
        if (ox, oy) not in self.cache:
            bw = (ox + ICON_W + 3) // 4
            bh = (oy + ICON_H + 3) // 4
            area = np.zeros((bh * 4, bw * 4, 4), dtype=np.uint8)
            area_pc = np.zeros((bh * 4, bw * 4), dtype=np.uint8)
            area[oy : oy + ICON_H, ox : ox + ICON_W] = self.rgba
            area_pc[oy : oy + ICON_H, ox : ox + ICON_W] = self.pc
            blocks = {}
            for by in range(bh):
                for bx in range(bw):
                    cell = area[by * 4 : by * 4 + 4, bx * 4 : bx * 4 + 4]
                    cell_pc = area_pc[by * 4 : by * 4 + 4, bx * 4 : bx * 4 + 4]
                    opaque = (cell[..., 3] > 0).reshape(-1)
                    bits = sum(1 << p for p in range(16) if opaque[p])
                    blocks[(bx, by)] = (sld.encode_bc1(cell), sld.encode_bc4(cell_pc), bits)
            self.cache[(ox, oy)] = (bw, bh, blocks)
        return self.cache[(ox, oy)]


def icon_position(frame: sld.Frame, bottom: int) -> tuple[int, int]:
    """Esquina superior izquierda del icono en el lienzo del frame."""
    return frame.hotspot_x - ICON_W // 2, frame.hotspot_y + bottom - ICON_H


def find_animals() -> dict[str, list[str]]:
    animals = defaultdict(list)
    for path in sorted(GAME_GRAPHICS.glob("a_herd_*_x1.sld")):
        m = ANIMATION_RE.match(path.name)
        if m:
            animals[m["animal"]].append(path.name)
    return dict(animals)


def add_icon(s: sld.SLD, bottom: int, icon: IconBlocks) -> int:
    """Añade el icono a todos los frames. Devuelve cuántos píxeles creció el lienzo hacia arriba."""
    # Si el icono no cabe en el lienzo, se agranda hacia arriba (múltiplo de 4
    # para no romper la rejilla de bloques).
    min_top = min(icon_position(f, bottom)[1] for f in s.frames)
    shift = (-min_top + 3) // 4 * 4 if min_top < 0 else 0

    prev: dict = {}
    for f in s.frames:
        main = f.layers["main"]
        pcl = f.layers.get("playercolor")
        mask = f.layers.get("mask")
        shadow = f.layers.get("shadow")

        # Rejillas completas (resolviendo la reutilización del frame anterior).
        # Se guarda una copia de la capa porque abajo se modifican sus límites.
        main_grid = sld.block_grid(main, prev.get("main"))
        prev["main"] = (copy.copy(main), main_grid)
        if pcl is not None:
            pc_grid = sld.block_grid(pcl, prev.get("playercolor"))
            prev["playercolor"] = (copy.copy(pcl), pc_grid)
        else:
            prev.pop("playercolor", None)

        if shift:
            f.height += shift
            f.hotspot_y += shift
            main.y1 += shift
            main.y2 += shift
            if shadow is not None:
                shadow.y1 += shift
                shadow.y2 += shift

        for v in (main.x1, main.y1, main.x2, main.y2):
            assert v % 4 == 0, "se esperaban límites alineados a 4 px"
        left, top = icon_position(f, bottom)
        ix1, iy1 = left // 4 * 4, top // 4 * 4
        abw, abh, blocks = icon.get(left - ix1, top - iy1)
        ix2, iy2 = ix1 + abw * 4, iy1 + abh * 4
        if iy2 > main.y1:
            raise SystemExit(f"El icono se solapa con el animal en el frame {f.frame_index}")

        nx1, ny1 = min(main.x1, ix1), min(main.y1, iy1)
        nx2, ny2 = max(main.x2, ix2), max(main.y2, iy2)
        nbw, nbh = (nx2 - nx1) // 4, (ny2 - ny1) // 4
        ox, oy = (main.x1 - nx1) // 4, (main.y1 - ny1) // 4  # posición del animal en la rejilla nueva
        bx0, by0 = (ix1 - nx1) // 4, (iy1 - ny1) // 4  # posición del icono en la rejilla nueva

        new_main = [None] * (nbw * nbh)
        new_pc = [None] * (nbw * nbh)
        for k, blk in enumerate(main_grid):
            by, bx = divmod(k, main.blocks_wide)
            new_main[(by + oy) * nbw + bx + ox] = blk
        if pcl is not None:
            for k, blk in enumerate(pc_grid):
                by, bx = divmod(k, main.blocks_wide)
                new_pc[(by + oy) * nbw + bx + ox] = blk
        for (bx, by), (bc1, bc4, _) in blocks.items():
            new_main[(by + by0) * nbw + bx + bx0] = bc1
            new_pc[(by + by0) * nbw + bx + bx0] = bc4

        if mask is not None:
            rows: list = []
            for r in range(nbh):
                if oy <= r < oy + main.blocks_high:
                    orig = mask.rows[r - oy]
                    rows.append([0] * ox + list(orig) + [0] * (nbw - ox - main.blocks_wide))
                elif by0 <= r < by0 + abh:
                    row = [0] * nbw
                    for bx in range(abw):
                        row[bx0 + bx] = blocks[(bx, r - by0)][2]
                    rows.append(row)
                else:
                    rows.append([None] * nbw)
            f.layers["mask"] = sld.MaskLayer(mask.header, rows)

        main.x1, main.y1, main.x2, main.y2 = nx1, ny1, nx2, ny2
        main.flag &= ~sld.FLAG_REUSE_PREVIOUS
        main.commands, main.blocks = sld.encode_grid(new_main)
        if pcl is None:
            pcl = sld.Layer("playercolor", 0, 0, 0, 0, 0x01, 0x01, [], [])
            f.layers["playercolor"] = pcl
        pcl.x1, pcl.y1, pcl.x2, pcl.y2 = nx1, ny1, nx2, ny2
        pcl.flag &= ~sld.FLAG_REUSE_PREVIOUS
        pcl.commands, pcl.blocks = sld.encode_grid(new_pc)
    return shift


def canvas_grids(s: sld.SLD, kind: str) -> list[dict]:
    """Por frame, {(x, y) del bloque en el lienzo: bloque} de una capa."""
    out = []
    prev = None
    for f in s.frames:
        layer = f.layers.get(kind)
        if layer is None:
            prev = None
            out.append({})
            continue
        grid = sld.block_grid(layer, prev)
        prev = (layer, grid)
        cells = {}
        for k, blk in enumerate(grid):
            if blk is not None:
                by, bx = divmod(k, layer.blocks_wide)
                cells[(layer.x1 + bx * 4, layer.y1 + by * 4)] = blk
        out.append(cells)
    return out


def verify(name: str, bottom: int, icon: IconBlocks, shift: int) -> None:
    """Relee el archivo escrito y comprueba, bloque a bloque, que el animal (imagen,
    color de jugador y sombra) está intacto y que el icono está en todos los frames."""
    before = sld.read(GAME_GRAPHICS / name)
    after = sld.read(OUT_DIR / name)
    assert len(before.frames) == len(after.frames)
    for kind in ("main", "playercolor", "shadow"):
        grids_b, grids_a = canvas_grids(before, kind), canvas_grids(after, kind)
        for fb, fa, gb, ga in zip(before.frames, after.frames, grids_b, grids_a):
            expected = {(x, y + shift): blk for (x, y), blk in gb.items()}
            if kind != "shadow":
                left, top = icon_position(fa, bottom)
                ix1, iy1 = left // 4 * 4, top // 4 * 4
                _, _, blocks = icon.get(left - ix1, top - iy1)
                for (bx, by), (bc1, bc4, _) in blocks.items():
                    blk = bc1 if kind == "main" else bc4
                    if blk is not None:
                        expected[(ix1 + bx * 4, iy1 + by * 4)] = blk
            if ga != expected:
                raise SystemExit(f"{name}: verificación fallida en la capa {kind}, frame {fb.frame_index}")


def preview_sheet(results: list[tuple[str, str, int]]) -> None:
    """Una imagen con todos los animales (primer frame caminando) en azul y gris."""
    tiles = []
    for animal, name, bottom in results:
        fr = decode_frames(OUT_DIR / name, limit=1)[0]
        hx, hy = fr["hotspot"]
        y0, y1, x0, x1 = hy + bottom - ICON_H - 6, hy + 30, hx - 45, hx + 45
        pair = []
        for color in ("azul", "gaia"):
            img = composite(fr, PLAYER_COLORS[color])
            pad = np.zeros((max(y1, img.shape[0]) - min(y0, 0), max(x1, img.shape[1]) - min(x0, 0), 3), np.uint8)
            pad[:] = (96, 128, 72)
            oy, ox = -min(y0, 0), -min(x0, 0)
            pad[oy : oy + img.shape[0], ox : ox + img.shape[1]] = img
            pair.append(pad[y0 + oy : y1 + oy, x0 + ox : x1 + ox])
        tile = np.concatenate([pair[0], np.full((pair[0].shape[0], 2, 3), 255, np.uint8), pair[1]], axis=1)
        tiles.append((animal, tile))
    cols = 4
    th = max(t.shape[0] for _, t in tiles)
    tw = max(t.shape[1] for _, t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    sheet = np.full((rows * (th + 4), cols * (tw + 4), 3), 255, np.uint8)
    for i, (_, t) in enumerate(tiles):
        r, c = divmod(i, cols)
        sheet[r * (th + 4) + th - t.shape[0] : r * (th + 4) + th, c * (tw + 4) : c * (tw + 4) + t.shape[1]] = t
    img = Image.fromarray(sheet)
    img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
    img.save(PREVIEW_DIR / "todos.png")
    print(f"vista previa: {PREVIEW_DIR / 'todos.png'} (orden: {', '.join(a for a, _ in tiles)})")


def install() -> None:
    target = LOCAL_MODS / INSTALL_NAME
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(MOD_DIR, target)
    print(f"instalado en {target}")


def main() -> None:
    rgba, pc = ICON_RGBA, ICON_PC
    icon = IconBlocks(rgba, pc)
    print(f"icono: {ICON_DESIGN} ({ICON_W}x{ICON_H} px)")

    PREVIEW_DIR.mkdir(exist_ok=True)
    Image.fromarray(rgba).resize((ICON_W * 12, ICON_H * 12), Image.NEAREST).save(PREVIEW_DIR / "icono.png")
    Image.fromarray(pc).resize((ICON_W * 12, ICON_H * 12), Image.NEAREST).save(PREVIEW_DIR / "icono_color_jugador.png")

    animals = find_animals()
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
        animals = {a: f for a, f in animals.items() if a in only}

    if only is None and OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "info.json", MOD_DIR / "info.json")  # título y descripción del mod

    results = []
    total_frames = 0
    for animal, names in animals.items():
        sprites = {name: sld.read(GAME_GRAPHICS / name) for name in names}
        # Misma altura en todas las animaciones del animal, para que el icono no salte
        # al pasar de quieto a caminando: justo encima del punto más alto del recuadro.
        bottom = min(f.layers["main"].y1 - f.hotspot_y for s in sprites.values() for f in s.frames) - GAP
        for name, s in sprites.items():
            shift = add_icon(s, bottom, icon)
            sld.write(s, OUT_DIR / name)
            verify(name, bottom, icon, shift)
            total_frames += len(s.frames)
        walk = next((n for n in names if "_walk" in n), names[0])
        results.append((animal, walk, bottom))
        print(f"{animal}: {len(names)} animaciones, icono a {-bottom} px sobre el suelo - verificado")
    print(f"total: {len(results)} animales, {total_frames} frames")

    preview_sheet(results)
    if "--install" in sys.argv:
        install()


if __name__ == "__main__":
    main()
