"""Muestra la estructura de uno o varios archivos SLD y comprueba la lectura/escritura.

Uso: py tools/inspect_sld.py archivo.sld [archivo2.sld ...] [--frames]
"""

import io
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sld  # noqa: E402


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_frames = "--frames" in sys.argv
    for path in args:
        s = sld.read(path)
        print(f"== {Path(path).name}")
        print(f"   versión {s.version}, frames {len(s.frames)}, unknowns {s.unknown1} {s.unknown2:#x} {s.unknown3:#x}")
        types = Counter(f.frame_type for f in s.frames)
        print(f"   tipos de frame: { {hex(k): v for k, v in types.items()} }")
        canvas = Counter((f.width, f.height, f.hotspot_x, f.hotspot_y) for f in s.frames)
        print(f"   lienzo (ancho, alto, hotspot x, y): {dict(canvas)}")
        flags = Counter(
            (k, l.flag, l.unknown) if k != "mask" else (k, l.header)
            for f in s.frames
            for k, l in f.layers.items()
        )
        print(f"   (capa, flag, unknown): {dict(flags)}")
        tops = [f.layers["main"].y1 - f.hotspot_y for f in s.frames if "main" in f.layers]
        lefts = [f.layers["main"].x1 - f.hotspot_x for f in s.frames if "main" in f.layers]
        rights = [f.layers["main"].x2 - f.hotspot_x for f in s.frames if "main" in f.layers]
        bottoms = [f.layers["main"].y2 - f.hotspot_y for f in s.frames if "main" in f.layers]
        print(f"   main respecto al hotspot: x {min(lefts)}..{max(rights)}, y {min(tops)}..{max(bottoms)}")
        if show_frames:
            for f in s.frames:
                parts = []
                for k, l in f.layers.items():
                    if k == "mask":
                        parts.append(f"mask[{l.header}]")
                        continue
                    parts.append(f"{k}[{l.x1},{l.y1}-{l.x2},{l.y2} f{l.flag:#x} cmd{len(l.commands)} blk{len(l.blocks)}]")
                print(f"   #{f.frame_index:3d} t{f.frame_type:#x} " + " ".join(parts))
        # Comprobación: leer y escribir debe dar el mismo archivo.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "roundtrip.sld"
            sld.write(s, out)
            same = out.read_bytes() == Path(path).read_bytes()
        print(f"   lectura/escritura idéntica: {'sí' if same else 'NO'}")


if __name__ == "__main__":
    main()
