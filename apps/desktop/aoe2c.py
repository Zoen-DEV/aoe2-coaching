"""AoE2 Coaching: el programa único (lo que empaqueta PyInstaller como AoE2Coaching.exe).

Abre el overlay de la partida y el panel, según cómo se lance:

    pyw aoe2c.py            desde el menú Inicio o el escritorio: animación y panel
    pyw aoe2c.py --inicio   desde el inicio con Windows: espera en la bandeja, sin panel

Si ya hay una copia abierta, no se abre otra: la que estaba muestra su panel.
Las preferencias, el historial y los logs están en %APPDATA%\\AoE2Coaching\\.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from overlay import main  # noqa: E402

if __name__ == "__main__":
    main()
