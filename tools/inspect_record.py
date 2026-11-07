"""Resume una repetición (.aoe2record) de AoE2 DE: mapa elegido y scripts XS cargados.

Sirve para comprobar, después de una prueba, si la partida se jugó en el mapa del
mod y si el juego cargó su script XS (el código de los .xs cargados queda guardado
en la cabecera de la repetición).

Uso: py tools/inspect_record.py [repeticion.aoe2record] [--buscar texto]

Sin archivo, usa la repetición más reciente de la carpeta savegame del perfil.
"""

import re
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "desktop"))
import rutas  # noqa: E402

SAVEGAME = rutas.para_scripts()[1] / "savegame"  # el perfil que usa AoE2C


def header(path: Path) -> bytes:
    data = path.read_bytes()
    size = struct.unpack("<I", data[:4])[0]
    return zlib.decompress(data[8:size], -15)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    search = None
    if "--buscar" in args:
        i = args.index("--buscar")
        search = args[i + 1]
        del args[i : i + 2]
    path = Path(args[0]) if args else max(SAVEGAME.glob("*.aoe2record"), key=lambda p: p.stat().st_mtime)
    raw = header(path)
    print(path.name)

    # Resumen de la configuración de la sala (texto en el idioma del juego).
    for key in ("Estilo de mapa", "Ubicación", "Map Style", "Location"):
        m = re.search(re.escape(key.encode("utf-8")) + rb": ([^\x00-\x1f]+)", raw)
        if m:
            print(f"  {key}: {m.group(1).decode('utf-8', 'replace')}")

    names = sorted({m.group(0).decode() for m in re.finditer(rb"[A-Za-z0-9_/\-]+\.xs\b", raw)})
    print("  scripts XS:", ", ".join(names) if names else "ninguno")

    # Funciones compiladas de cada script propio. El juego guarda las variables de
    # cada función compilada como "<script>$<función><n>$<variable>", donde n es el
    # orden de la función en el archivo. Si la compilación falla, solo aparecen las
    # funciones anteriores al error.
    for name in names:
        script = name[:-3]
        if script in ("Constants", "Effects") or script.startswith("ailib/"):
            continue
        found = {}
        for m in re.finditer(re.escape(script.encode()) + rb"\$([A-Za-z_]\w*?)(\d+)\$", raw):
            found[int(m.group(2))] = m.group(1).decode()
        compiled = [found[i] for i in sorted(found)]
        print(f"  {name}: {len(compiled)} funciones compiladas (con variables): {', '.join(compiled) or 'ninguna'}")

    if search:
        count = raw.count(search.encode("utf-8"))
        print(f"  '{search}': {count} apariciones")


if __name__ == "__main__":
    main()
