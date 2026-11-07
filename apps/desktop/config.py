"""Preferencias de AoE2C, compartidas por el overlay y el panel (config.json).

Las dos ventanas viven en el mismo proceso y usan el mismo diccionario: lo que se
cambia en el panel se ve en la guía de la partida sin reiniciar nada.
"""

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVO = HERE / "config.json"

DEFECTO = {
    # Guía en partida (overlay).
    "posicion": "derecha",          # derecha (sobre el marcador) o izquierda
    "plegado": False,
    "pestana_historial": True,      # pestaña HISTORIAL fuera de partida
    "opacidad": 1.0,                # opacidad de la tarjeta de la guía (0.6 a 1)
    "pasos_siguientes": None,       # pasos de "A continuación"; None = lo que diga la guía
    "aviso_casas": True,
    "abrir_historial_al_terminar": True,
    # Panel.
    "guia_activa": "fast_castle",   # la que cargan los mapas [AoE2C] (aoe2c_guia.xs)
    "idioma": "es",
    "abrir_panel_al_iniciar": True,
    "aviso_bandeja_visto": False,   # el aviso "sigue en la bandeja" sale una sola vez
}


def cargar(archivo: Path = ARCHIVO) -> dict:
    try:
        datos = json.loads(Path(archivo).read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            datos = {}
    except (OSError, ValueError):
        datos = {}
    return {**DEFECTO, **{k: v for k, v in datos.items() if k in DEFECTO}}


def guardar(config: dict, archivo: Path = ARCHIVO) -> None:
    archivo = Path(archivo)
    tmp = archivo.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, archivo)
    except OSError:
        pass
