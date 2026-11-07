"""Lectura y escritura del formato de sprites SLD de AoE2 DE.

Estructura del archivo:
- Cabecera de 16 bytes ("SLDX", versión, número de frames...).
- Por cada frame: cabecera de 12 bytes y luego sus capas, en este orden
  si están presentes: main, shadow, unknown, damage, playercolor.
- Cada capa guarda la imagen en bloques de 4x4 píxeles comprimidos
  (8 bytes por bloque: BC1 para main/damage, BC4 para el resto) y una
  lista de comandos (saltar N bloques, dibujar M bloques).
- Excepción: la capa 0x04 ("mask") es una máscara de 1 bit alineada con
  la rejilla de bloques de main. Se guarda fila a fila: un byte < 0x80 salta
  N bloques y un byte >= 0x80 dibuja (byte & 0x7F) bloques de 2 bytes
  (16 bits, uno por píxel). Una tabla al principio da dónde empieza cada fila.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

import numpy as np

LAYER_ORDER = [
    (0x01, "main"),
    (0x02, "shadow"),
    (0x04, "mask"),
    (0x08, "damage"),
    (0x10, "playercolor"),
]
# Capas con sus propios límites. damage, playercolor y mask usan los de main.
BOUNDED = {"main", "shadow"}
# Capas en BC1 (color). El resto son BC4 (un canal).
BC1_LAYERS = {"main", "damage"}
# Si este bit está activo, los bloques saltados se copian del frame anterior.
FLAG_REUSE_PREVIOUS = 0x80


@dataclass
class Layer:
    kind: str
    x1: int
    y1: int
    x2: int
    y2: int
    flag: int
    unknown: int
    commands: list[tuple[int, int]]
    blocks: list[bytes]

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def blocks_wide(self) -> int:
        return (self.width + 3) // 4

    @property
    def blocks_high(self) -> int:
        return (self.height + 3) // 4


@dataclass
class MaskLayer:
    """Capa 0x04: máscara de 1 bit. `rows` tiene, por cada fila de bloques de main,
    una lista con el valor de 16 bits de cada bloque o None si está vacío."""

    header: tuple[int, int]
    rows: list[list]
    kind: str = "mask"
    # Bytes originales; se reutilizan al escribir si la máscara no se modificó.
    raw: bytes | None = None


@dataclass
class Frame:
    width: int
    height: int
    hotspot_x: int
    hotspot_y: int
    frame_type: int
    unknown5: int
    frame_index: int
    layers: dict[str, Layer] = field(default_factory=dict)


@dataclass
class SLD:
    version: int
    unknown1: int
    unknown2: int
    unknown3: int
    frames: list[Frame]


def _align4(n: int) -> int:
    return (n + 3) & ~3


def read(path) -> SLD:
    data = open(path, "rb").read()
    sig, version, nframes, u1, u2, u3 = struct.unpack_from("<4sHHHHI", data, 0)
    if sig != b"SLDX":
        raise ValueError(f"{path}: no es un archivo SLD (firma {sig!r})")
    pos = 16
    frames = []
    for _ in range(nframes):
        w, h, hx, hy, ftype, u5, fidx = struct.unpack_from("<HHHHBBH", data, pos)
        pos += 12
        frame = Frame(w, h, hx, hy, ftype, u5, fidx)
        for bit, kind in LAYER_ORDER:
            if not ftype & bit:
                continue
            start = pos
            (length,) = struct.unpack_from("<I", data, pos)
            p = pos + 4
            if kind == "mask":
                frame.layers[kind] = _read_mask(data[p : start + length], frame.layers["main"], path)
                pos = start + _align4(length)
                continue
            if kind in BOUNDED:
                x1, y1, x2, y2, flag, unk = struct.unpack_from("<HHHHBB", data, p)
                p += 10
            else:
                main = frame.layers["main"]
                x1, y1, x2, y2 = main.x1, main.y1, main.x2, main.y2
                flag, unk = struct.unpack_from("<BB", data, p)
                p += 2
            (ncmd,) = struct.unpack_from("<H", data, p)
            p += 2
            cmds = [struct.unpack_from("<BB", data, p + 2 * k) for k in range(ncmd)]
            p += 2 * ncmd
            ndraw = sum(d for _, d in cmds)
            blocks = [data[p + 8 * k : p + 8 * k + 8] for k in range(ndraw)]
            p += 8 * ndraw
            if p - start != length:
                raise ValueError(
                    f"{path}: capa {kind} del frame {fidx} mide {p - start} bytes, "
                    f"la cabecera dice {length}"
                )
            frame.layers[kind] = Layer(kind, x1, y1, x2, y2, flag, unk, cmds, blocks)
            pos = start + _align4(length)
        frames.append(frame)
    if pos != len(data):
        raise ValueError(f"{path}: sobran {len(data) - pos} bytes al final")
    return SLD(version, u1, u2, u3, frames)


def write(sld: SLD, path) -> None:
    out = bytearray()
    out += struct.pack(
        "<4sHHHHI", b"SLDX", sld.version, len(sld.frames), sld.unknown1, sld.unknown2, sld.unknown3
    )
    for frame in sld.frames:
        ftype = 0
        for bit, kind in LAYER_ORDER:
            if kind in frame.layers:
                ftype |= bit
        out += struct.pack(
            "<HHHHBBH",
            frame.width,
            frame.height,
            frame.hotspot_x,
            frame.hotspot_y,
            ftype,
            frame.unknown5,
            frame.frame_index,
        )
        for _, kind in LAYER_ORDER:
            layer = frame.layers.get(kind)
            if layer is None:
                continue
            body = bytearray()
            if kind == "mask":
                body += _write_mask(layer)
            elif kind in BOUNDED:
                body += struct.pack(
                    "<HHHHBB", layer.x1, layer.y1, layer.x2, layer.y2, layer.flag, layer.unknown
                )
            else:
                body += struct.pack("<BB", layer.flag, layer.unknown)
            if kind != "mask":
                body += struct.pack("<H", len(layer.commands))
                for skip, draw in layer.commands:
                    body += struct.pack("<BB", skip, draw)
                for block in layer.blocks:
                    body += block
            length = 4 + len(body)
            out += struct.pack("<I", length) + body
            out += b"\0" * (_align4(length) - length)
    with open(path, "wb") as f:
        f.write(out)


# ---------------------------------------------------------------------------
# Capa máscara (0x04)
# ---------------------------------------------------------------------------


def _read_mask(buf: bytes, main: Layer, path) -> MaskLayer:
    header = struct.unpack_from("<HH", buf, 0)
    nrows = main.blocks_high
    starts = [0] + list(struct.unpack_from(f"<{nrows - 1}H", buf, 4))
    data = buf[4 + 2 * (nrows - 1) :]
    ends = starts[1:] + [len(data)]
    rows = []
    for r in range(nrows):
        row: list = []
        p = starts[r]
        while p < ends[r]:
            cmd = data[p]
            p += 1
            if cmd & 0x80:
                for _ in range(cmd & 0x7F):
                    row.append(int.from_bytes(data[p : p + 2], "little"))
                    p += 2
            else:
                row.extend([None] * cmd)
        if len(row) != main.blocks_wide:
            raise ValueError(
                f"{path}: la fila {r} de la máscara tiene {len(row)} bloques, main tiene {main.blocks_wide}"
            )
        rows.append(row)
    return MaskLayer(header, rows, raw=bytes(buf))


def _write_mask(mask: MaskLayer) -> bytes:
    if mask.raw is not None:
        return mask.raw
    encoded_rows = []
    for row in mask.rows:
        out = bytearray()
        i = 0
        while i < len(row):
            if row[i] is None:
                n = 0
                while i < len(row) and row[i] is None and n < 0x7F:
                    n += 1
                    i += 1
                out.append(n)
            else:
                vals = []
                while i < len(row) and row[i] is not None and len(vals) < 0x7F:
                    vals.append(row[i])
                    i += 1
                out.append(0x80 | len(vals))
                for v in vals:
                    out += v.to_bytes(2, "little")
        encoded_rows.append(bytes(out))
    starts = []
    pos = 0
    for enc in encoded_rows[:-1]:
        pos += len(enc)
        starts.append(pos)
    body = struct.pack("<HH", *mask.header)
    body += struct.pack(f"<{len(starts)}H", *starts)
    body += b"".join(encoded_rows)
    return body


def mask_from_main(grid: list, alpha: np.ndarray, blocks_wide: int, blocks_high: int, header=(5, 0)) -> MaskLayer:
    """Crea la máscara a partir de la rejilla de main: un bloque vacío en main queda vacío
    en la máscara; el resto guarda qué píxeles son opacos (bit p = píxel (p // 4, p % 4))."""
    padded = np.zeros((blocks_high * 4, blocks_wide * 4), dtype=bool)
    padded[: alpha.shape[0], : alpha.shape[1]] = alpha > 0
    rows = []
    for by in range(blocks_high):
        row: list = []
        for bx in range(blocks_wide):
            if grid[by * blocks_wide + bx] is None:
                row.append(None)
                continue
            cell = padded[by * 4 : by * 4 + 4, bx * 4 : bx * 4 + 4].reshape(-1)
            row.append(sum(1 << p for p in range(16) if cell[p]))
        rows.append(row)
    return MaskLayer(header, rows)


# ---------------------------------------------------------------------------
# Bloques: posición en la rejilla de la capa
# ---------------------------------------------------------------------------


def block_grid(layer: Layer, previous: tuple[Layer, list] | None = None) -> list:
    """Devuelve una lista (fila a fila) con el bloque de cada celda o None si está vacía.

    Si la capa tiene el flag de reutilizar, las celdas saltadas toman el bloque que
    había en la misma posición del lienzo en `previous` = (capa, rejilla) del mismo
    tipo en el frame anterior.
    """
    bw = layer.blocks_wide
    total = bw * layer.blocks_high
    grid: list = [None] * total
    i = 0
    b = 0
    reuse = layer.flag & FLAG_REUSE_PREVIOUS and previous is not None
    for skip, draw in layer.commands:
        if reuse:
            prev_layer, prev_grid = previous
            for k in range(i, i + skip):
                by, bx = divmod(k, bw)
                px = (layer.x1 + bx * 4 - prev_layer.x1) // 4
                py = (layer.y1 + by * 4 - prev_layer.y1) // 4
                if 0 <= px < prev_layer.blocks_wide and 0 <= py < prev_layer.blocks_high:
                    grid[k] = prev_grid[py * prev_layer.blocks_wide + px]
        i += skip
        for _ in range(draw):
            grid[i] = layer.blocks[b]
            i += 1
            b += 1
    return grid


def encode_grid(grid: list) -> tuple[list[tuple[int, int]], list[bytes]]:
    """Convierte una rejilla de bloques (None = vacío) en comandos y bloques."""
    commands: list[tuple[int, int]] = []
    blocks: list[bytes] = []
    i = 0
    n = len(grid)
    while i < n:
        skip = 0
        while i < n and grid[i] is None and skip < 255:
            skip += 1
            i += 1
        draw = 0
        while i < n and grid[i] is not None and draw < 255:
            blocks.append(grid[i])
            draw += 1
            i += 1
        commands.append((skip, draw))
    return commands, blocks


# ---------------------------------------------------------------------------
# Descompresión BC1 / BC4
# ---------------------------------------------------------------------------


def _rgb565(c: int) -> np.ndarray:
    r = (c >> 11) & 0x1F
    g = (c >> 5) & 0x3F
    b = c & 0x1F
    return np.array([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], dtype=np.float64)


def decode_bc1(block: bytes) -> np.ndarray:
    """Bloque BC1 de 8 bytes -> array 4x4x4 (RGBA, uint8)."""
    c0, c1, idx = struct.unpack("<HHI", block)
    a, b = _rgb565(c0), _rgb565(c1)
    if c0 > c1:
        palette = [
            np.append(a, 255),
            np.append(b, 255),
            np.append((2 * a + b) / 3, 255),
            np.append((a + 2 * b) / 3, 255),
        ]
    else:
        palette = [np.append(a, 255), np.append(b, 255), np.append((a + b) / 2, 255), np.zeros(4)]
    out = np.zeros((4, 4, 4), dtype=np.uint8)
    for p in range(16):
        out[p // 4, p % 4] = np.round(palette[(idx >> (2 * p)) & 3])
    return out


def decode_bc4(block: bytes) -> np.ndarray:
    """Bloque BC4 de 8 bytes -> array 4x4 (uint8)."""
    r0, r1 = block[0], block[1]
    bits = int.from_bytes(block[2:8], "little")
    if r0 > r1:
        palette = [r0, r1] + [((7 - k) * r0 + k * r1) / 7 for k in range(1, 7)]
    else:
        palette = [r0, r1] + [((5 - k) * r0 + k * r1) / 5 for k in range(1, 5)] + [0, 255]
    out = np.zeros((4, 4), dtype=np.uint8)
    for p in range(16):
        out[p // 4, p % 4] = round(palette[(bits >> (3 * p)) & 7])
    return out


# ---------------------------------------------------------------------------
# Compresión BC1 / BC4 (para bloques nuevos, como el icono)
# ---------------------------------------------------------------------------


def _to565(rgb) -> int:
    r, g, b = (int(v) for v in rgb)
    return ((r * 31 + 127) // 255) << 11 | ((g * 63 + 127) // 255) << 5 | ((b * 31 + 127) // 255)


def encode_bc1(block: np.ndarray) -> bytes | None:
    """Bloque 4x4x4 RGBA (alfa 0 o 255) -> 8 bytes BC1. None si es totalmente transparente.

    Prueba todas las parejas de colores del bloque como extremos y se queda con la de
    menor error. Pensado para bloques con pocos colores (iconos), no para fotos.
    """
    px = block.reshape(16, 4).astype(np.int64)
    opaque = px[:, 3] > 0
    if not opaque.any():
        return None
    has_transparent = not opaque.all()
    candidates = sorted({_to565(p[:3]) for p in px[opaque]})
    best = None
    for i, a in enumerate(candidates):
        for b in candidates[i:]:
            for c0, c1 in ((a, b), (b, a)):
                four = c0 > c1
                if has_transparent and four:
                    continue
                e0, e1 = _rgb565(c0), _rgb565(c1)
                if four:
                    pal = [e0, e1, (2 * e0 + e1) / 3, (e0 + 2 * e1) / 3]
                else:
                    pal = [e0, e1, (e0 + e1) / 2]
                pal = np.array(pal)
                d = ((px[:, None, :3] - pal[None, :, :]) ** 2).sum(axis=2)
                idx = d.argmin(axis=1)
                err = d[np.arange(16), idx][opaque].sum()
                if not four:
                    idx = np.where(opaque, idx, 3)
                if best is None or err < best[0]:
                    best = (err, c0, c1, idx)
    _, c0, c1, idx = best
    bits = 0
    for p in range(16):
        bits |= int(idx[p]) << (2 * p)
    return struct.pack("<HHI", c0, c1, bits)


def encode_bc4(block: np.ndarray) -> bytes | None:
    """Bloque 4x4 de un canal -> 8 bytes BC4. None si es todo cero."""
    v = block.reshape(16).astype(np.float64)
    if not v.any():
        return None
    hi, lo = int(v.max()), int(v.min())
    if hi == lo:
        r0, r1 = hi, lo
        pal = np.array([hi] * 8, dtype=np.float64)
    else:
        r0, r1 = hi, lo
        pal = np.array([r0, r1] + [((7 - k) * r0 + k * r1) / 7 for k in range(1, 7)])
    idx = np.abs(v[:, None] - pal[None, :]).argmin(axis=1)
    bits = 0
    for p in range(16):
        bits |= int(idx[p]) << (3 * p)
    return bytes([r0, r1]) + bits.to_bytes(6, "little")


def decode_layer(layer: Layer, grid: list) -> np.ndarray:
    """Rejilla de bloques -> imagen (RGBA para BC1, un canal para BC4)."""
    bw, bh = layer.blocks_wide, layer.blocks_high
    if layer.kind in BC1_LAYERS:
        img = np.zeros((bh * 4, bw * 4, 4), dtype=np.uint8)
        dec = decode_bc1
    else:
        img = np.zeros((bh * 4, bw * 4), dtype=np.uint8)
        dec = decode_bc4
    for i, block in enumerate(grid):
        if block is None:
            continue
        y, x = divmod(i, bw)
        img[y * 4 : y * 4 + 4, x * 4 : x * 4 + 4] = dec(block)
    return img[: layer.height, : layer.width]
