"""Crea un juego falso para GitHub Actions, donde no está AoE2 DE.

    py .github/scripts/juego_falso.py CARPETA

Escribe en CARPETA/juego_falso/AoE2DE el .exe y los .rms "oficiales" de mapas.json
(inventados, los mismos que usan las pruebas) e imprime la ruta del juego. Con
AOE2C_JUEGO=<esa ruta>, content/guias/build.py arma las guías y los mapas sin el juego.

Los mapas armados así no sirven para jugar, pero no se publican: el catálogo solo lleva
las guías (manifiesto + .xs, que no dependen del juego) y las recetas de los mapas.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "apps" / "desktop" / "pruebas"))
from apoyo import juego_falso  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(juego_falso(Path(sys.argv[1]).resolve()))
