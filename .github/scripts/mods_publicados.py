"""Descarga los paquetes de mods ya publicados, para el proceso contenido.yml.

    py .github/scripts/mods_publicados.py CARPETA

Los mods (como el de las ovejas) se arman con los sprites del juego, que no está en
GitHub Actions. Por eso el catálogo reutiliza el .zip ya armado: este script baja a
CARPETA los mod-<id>-<versión>.zip de

1. la última publicación contenido-* (los mods que no cambiaron de versión), y
2. la publicación "mods-fuente", donde se sube a mano el .zip de una versión nueva
   (ver docs/03-plan-compartir-aoe2c.md, "Publicación automática").

Después, `py content/catalogo.py --mods-previos CARPETA` usa el .zip de cada mod que no
esté armado en build/mods. Usa GITHUB_TOKEN y GITHUB_REPOSITORY si están.
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY") or "Zoen-DEV/aoe2-coaching"
API = f"https://api.github.com/repos/{REPO}"
FUENTE = "mods-fuente"
PAQUETE = re.compile(r"^mod-[a-z0-9_-]+-\d+(\.\d+)*\.zip$")


def pedir(url: str, json_api: bool = True) -> bytes:
    cabeceras = {"User-Agent": "aoe2c-publicacion"}
    if json_api:
        cabeceras["Accept"] = "application/vnd.github+json"
    if os.environ.get("GITHUB_TOKEN"):
        cabeceras["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=cabeceras), timeout=60) as r:
        return r.read()


def publicaciones() -> list[dict]:
    """La última contenido-* publicada y la de mods-fuente (si existen)."""
    todas = json.loads(pedir(f"{API}/releases?per_page=100"))
    contenido = [p for p in todas if str(p.get("tag_name", "")).startswith("contenido-")
                 and not p.get("draft") and not p.get("prerelease")]
    elegidas = sorted(contenido, key=lambda p: p.get("published_at") or "", reverse=True)[:1]
    elegidas += [p for p in todas if p.get("tag_name") == FUENTE]
    return elegidas


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    carpeta = Path(sys.argv[1])
    carpeta.mkdir(parents=True, exist_ok=True)
    for p in publicaciones():
        for a in p.get("assets") or []:
            nombre = str(a.get("name", ""))
            if PAQUETE.match(nombre):  # la de mods-fuente va después: gana si hay dos iguales
                (carpeta / nombre).write_bytes(pedir(a["browser_download_url"], json_api=False))
                print(f"{p['tag_name']}: {nombre}")
    if not any(carpeta.glob("mod-*.zip")):
        print("no hay mods publicados")


if __name__ == "__main__":
    main()
