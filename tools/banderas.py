"""Genera apps/desktop/banderas_datos.py con los SVG de flag-icons (licencia MIT).

    py tools/banderas.py <carpeta del paquete flag-icons>

La carpeta es la del paquete de npm descomprimido (la que tiene flags/4x3 y LICENSE):
https://registry.npmjs.org/flag-icons/-/flag-icons-<versión>.tgz. El panel Match Info
dibuja la bandera del país que da la API (código de dos letras), así que solo se
guardan esas (sin regiones como es-ct). Los SVG se compactan (sin comentarios ni
espacios entre etiquetas) pero el dibujo no cambia. El resultado se sube a git.
"""

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "apps" / "desktop" / "banderas_datos.py"
RE_CODIGO = re.compile(r"[a-z]{2}")


def compactar(svg: str) -> str:
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r">\s+<", "><", svg)
    return re.sub(r"\s+", " ", svg).strip()


def main(args: list[str]) -> None:
    if not args:
        sys.exit(__doc__)
    paquete = Path(args[0])
    carpeta = paquete / "flags" / "4x3"
    if not carpeta.is_dir():
        sys.exit(f"no está {carpeta}: ¿es la carpeta del paquete flag-icons?")
    version = json.loads((paquete / "package.json").read_text(encoding="utf-8"))["version"]
    licencia = (paquete / "LICENSE").read_text(encoding="utf-8").strip()
    svgs = {p.stem: compactar(p.read_text(encoding="utf-8")) for p in sorted(carpeta.glob("*.svg"))
            if RE_CODIGO.fullmatch(p.stem)}
    filas = "".join(f"    {codigo!r}: {svg.encode('utf-8')!r},\n" for codigo, svg in svgs.items())
    aviso = "\n".join(("# " + linea).rstrip() for linea in licencia.splitlines())
    SALIDA.write_text(
        f'"""Banderas de los países (SVG 4:3) para el panel Match Info. Ver banderas.py.\n\n'
        f"Generado por tools/banderas.py con flag-icons {version} "
        f'(https://github.com/lipis/flag-icons); no editar a mano."""\n\n'
        f"# Licencia de flag-icons:\n#\n{aviso}\n\n"
        f"SVG: dict[str, bytes] = {{\n{filas}}}\n",
        encoding="utf-8", newline="\n")
    print(f"{len(svgs)} banderas ({SALIDA.stat().st_size // 1024} KB) -> {SALIDA}")


if __name__ == "__main__":
    main(sys.argv[1:])
