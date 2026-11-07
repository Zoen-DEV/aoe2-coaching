"""AoE2 Coaching: el programa único (lo que empaqueta PyInstaller como AoE2Coaching.exe).

Abre el overlay de la partida y el panel, según cómo se lance:

    pyw aoe2c.py            desde el menú Inicio o el escritorio: animación y panel
    pyw aoe2c.py --inicio   desde el inicio con Windows: espera en la bandeja, sin panel

Si ya hay una copia abierta, no se abre otra: la que estaba muestra su panel.
Las preferencias, el historial y los logs están en %APPDATA%\\AoE2Coaching\\.

Órdenes para el instalador (sin ventanas):

    --salir                          cierra la copia abierta y espera a que termine
    --desinstalar [--juego] [--datos]  ver desinstalar.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def orden_instalador(args: list[str]) -> int | None:
    """Ejecuta una orden del instalador y devuelve su código de salida, o None si no es una."""
    if "--salir" in args:
        from overlay import pedir_salir
        return 0 if pedir_salir() else 1
    if "--desinstalar" in args:
        import rutas
        rutas.configurar_log()
        from overlay import pedir_salir
        pedir_salir()
        import desinstalar
        return desinstalar.main(args)
    return None


if __name__ == "__main__":
    codigo = orden_instalador(sys.argv[1:])
    if codigo is not None:
        sys.exit(codigo)
    from overlay import main
    main()
