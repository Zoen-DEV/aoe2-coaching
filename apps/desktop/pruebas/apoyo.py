"""Contenido de prueba compartido por las pruebas: un juego falso y un catálogo pequeño.

- juego_falso(): una carpeta con AoE2DE_s.exe, los .rms "oficiales" de mapas.json
  (inventados) y sus imágenes de la sala. Así los mapas se arman sin el juego real.
- catalogo_de_prueba(): las guías de build/ (las genera content/guias/build.py), los
  mapas de mapas.json, un mod inventado pequeño y otro que pide una app más nueva.
- instalador_de_prueba(): un Instalador con todo en carpetas temporales y las guías
  del catálogo ya instaladas.
"""

import importlib.util
import json
import struct
import sys
import zlib
from pathlib import Path

OVERLAY = Path(__file__).resolve().parent.parent  # apps/desktop
RAIZ = OVERLAY.parent.parent
sys.path.insert(0, str(OVERLAY))

import catalogo as K  # noqa: E402
import instalador as I  # noqa: E402
import mapas as M  # noqa: E402
import rutas  # noqa: E402
import textos  # noqa: E402

# Las pruebas comprueban los textos en español: el idioma inicial no depende del de
# Windows (en GitHub Actions, Windows está en inglés).
textos.idioma_de_windows = lambda: "es"

MAPAS = json.loads((RAIZ / "content" / "mapas" / "mapas.json").read_text(encoding="utf-8"))["mapas"]
MOD_PRUEBA = "icono-prueba"


def _generador():
    spec = importlib.util.spec_from_file_location("generador_catalogo", RAIZ / "content" / "catalogo.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def png(ruta: Path, w: int = 24, h: int = 24) -> Path:
    """Un PNG liso, sin Qt."""
    def bloque(tipo: bytes, datos: bytes) -> bytes:
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos))
    filas = b"".join(b"\x00" + b"\x50\x80\x30" * w for _ in range(h))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(b"\x89PNG\r\n\x1a\n" + bloque(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + bloque(b"IDAT", zlib.compress(filas)) + bloque(b"IEND", b""))
    return ruta


def juego_falso(tmp: Path) -> Path:
    juego = tmp / "juego_falso" / "AoE2DE"
    (juego / rutas.EXE_JUEGO).parent.mkdir(parents=True, exist_ok=True)
    (juego / rutas.EXE_JUEGO).write_bytes(b"MZ")
    for m in MAPAS:
        oficial = juego / M.MAPAS_OFICIALES / m["base"]
        oficial.parent.mkdir(parents=True, exist_ok=True)
        oficial.write_bytes(f"/* {m['base']} oficial (de prueba) */\r\n<PLAYER_SETUP>\r\n".encode("ascii"))
        png(juego / M.ICONOS_OFICIALES / (m.get("imagen") or f"rm_{Path(m['base']).stem.lower()}.png"))
    return juego


def catalogo_de_prueba(tmp: Path) -> Path:
    """Escribe tmp/catalogo/catalogo.json con sus paquetes y devuelve su ruta."""
    gen = _generador()
    salida = tmp / "catalogo"
    salida.mkdir(parents=True, exist_ok=True)
    mod = tmp / "mod_prueba"
    (mod / "resources" / "_common" / "drs" / "graphics").mkdir(parents=True, exist_ok=True)
    (mod / "info.json").write_text('{"Title": "Icono de prueba", "Description": "", "Author": "prueba"}', encoding="utf-8")
    (mod / "resources" / "_common" / "drs" / "graphics" / "a_prueba_x1.sld").write_bytes(b"SLDX" + bytes(64))
    archivos = [(p.relative_to(mod).as_posix(), p) for p in mod.rglob("*") if p.is_file()]
    textos = {"es": "Icono de prueba", "en": "Test marker"}
    elementos = gen.guias(salida) + gen.mapas() + [
        K.Elemento("mod", MOD_PRUEBA, "1.0.0", "1.0.0", textos, textos,
                   {"carpeta": MOD_PRUEBA, "titulo": "Icono de prueba"},
                   gen.zip_fijo(salida / f"mod-{MOD_PRUEBA}-1.0.0.zip", archivos)),
        K.Elemento("mod", "mod-futuro", "1.0.0", "99.0.0", textos, textos,
                   {"carpeta": "mod-futuro", "titulo": "Mod del futuro"},
                   gen.zip_fijo(salida / "mod-mod-futuro-1.0.0.zip", archivos)),
    ]
    ruta = salida / K.NOMBRE
    ruta.write_text(K.a_json(K.Catalogo(elementos), "2026-11-07T00:00:00Z"), encoding="utf-8")
    return ruta


def instalador_de_prueba(tmp: Path, nombre: str, guias: bool = True, juego: bool = True) -> I.Instalador:
    """Instalador con perfil, contenido y juego en tmp/<nombre>, y las guías instaladas."""
    base = tmp / nombre
    ruta = catalogo_de_prueba(base)
    cat = K.leer(ruta.read_bytes(), str(ruta), estricto=True)
    inst = I.Instalador(perfil=base / "perfil", juego=juego_falso(base) if juego else None,
                        contenido=base / "contenido", catalogo=cat)
    if guias:
        for e in cat.de("guia"):
            paquete = K.descargar_paquete(cat, e, inst.descargas)
            error = inst.instalar_guia(e, paquete)
            if error:
                raise AssertionError(f"no se pudo instalar la guía de prueba {e.id}: {error}")
    return inst
