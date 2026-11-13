"""Preferencias de AoE2C, compartidas por el overlay y el panel (config.json en
%APPDATA%/AoE2Coaching/, ver rutas.py).

Las dos ventanas viven en el mismo proceso y usan el mismo diccionario: lo que se
cambia en el panel se ve en la guía de la partida sin reiniciar nada.
"""

import json
import os
from pathlib import Path

import rutas
import textos

ARCHIVO = rutas.CONFIG

DEFECTO = {
    # Guía en partida (overlay).
    "posicion": "derecha",          # derecha (sobre el marcador) o izquierda
    "plegado": False,
    "pestana_historial": True,      # pestaña HISTORIAL fuera de partida
    "opacidad": 1.0,                # opacidad de la tarjeta de la guía (0.6 a 1)
    "pasos_siguientes": None,       # pasos de "A continuación"; None = lo que diga la guía
    "aviso_casas": True,
    "abrir_historial_al_terminar": True,
    # Match Info: jugadores y elo en las partidas clasificatorias (match_ui.py).
    "match_info": True,
    "match_lado": "derecha",        # borde al que va pegado: derecha o izquierda
    "match_altura": None,           # fracción de la pantalla desde arriba; None = la de match_ui.ALTURA
    "match_winrate": True,
    "match_elo_max": False,
    "match_diferencia": True,       # en 1v1, elo del rival frente al propio
    "match_atajo": "Ctrl+Alt+M",    # mostrar u ocultar el panel durante la partida
    "match_perfil": None,           # ID de perfil elegido a mano (None = el deducido)
    "match_perfil_detectado": None, # el deducido de las repeticiones (vigilante.perfil_propio)
    # Panel.
    "guia_activa": "fast_castle",   # la que cargan los mapas [AoE2C] (aoe2c_guia.xs)
    "idioma": None,                 # es o en; None = el de Windows (la primera vez)
    "abrir_panel_al_iniciar": True,
    "aviso_bandeja_visto": False,   # el aviso "sigue en la bandeja" sale una sola vez
    # Carpetas (None = se buscan solas, ver rutas.py).
    "perfil": None,                 # carpeta del perfil elegida (si hay varias)
    "juego": None,                  # carpeta del juego elegida a mano (si no se encuentra)
}


def cargar(archivo: Path = ARCHIVO) -> dict:
    try:
        datos = json.loads(Path(archivo).read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            datos = {}
    except (OSError, ValueError):
        datos = {}
    config = {**DEFECTO, **{k: v for k, v in datos.items() if k in DEFECTO}}
    if config["idioma"] not in textos.IDIOMAS:
        config["idioma"] = textos.idioma_de_windows()
    return config


def guardar(config: dict, archivo: Path = ARCHIVO) -> None:
    archivo = Path(archivo)
    tmp = archivo.with_suffix(".tmp")
    try:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, archivo)
    except OSError:
        pass
