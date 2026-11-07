"""Lo que hace AoE2C al desinstalarse (lo llama el desinstalador de Inno Setup).

    AoE2Coaching.exe --desinstalar [--juego] [--datos]

- Siempre: quita AoE2C del inicio con Windows.
- --juego: quita del juego lo que puso AoE2C, en todos los perfiles: los scripts de las
  guías (aoe2c_guia.xs y guia_<id>.xs), el mod de los mapas [AoE2C], los mods
  instalados desde el panel y sus líneas de mod-status.json. Las demás líneas y los
  mods de otros autores no se tocan. Con el juego abierto no hace nada (código 2):
  el desinstalador pide cerrarlo.
- --datos: borra %APPDATA%\\AoE2Coaching (preferencias, historial, logs y contenido).

Códigos de salida: 0 bien, 1 algo falló (sigue con lo demás), 2 el juego está abierto.
"""

import logging
import shutil
import sys
from pathlib import Path

import catalogo as K
import instalador as I
import rutas
from lector import cargar_guias

BIEN, FALLO, JUEGO_ABIERTO = 0, 1, 2
log = logging.getLogger("aoe2c")


def _mods_de_aoe2c(contenido: Path, perfil: Path) -> list[tuple[str, str]]:
    """(carpeta, título) de los mods que el panel instaló en este perfil."""
    estado = I.Instalador(perfil=perfil, contenido=contenido)._estado()
    instalados = estado["mods"].get(I._clave(perfil), {})
    cat = K.cargar_copia(contenido)
    out = []
    for id_ in instalados:
        e = cat.buscar("mod", id_) if cat else None
        carpeta, titulo = (e.datos["carpeta"], e.datos["titulo"]) if e else (id_, id_)
        if K.RE_ID.fullmatch(carpeta):  # nunca una ruta: solo un nombre de carpeta
            out.append((carpeta, titulo))
    return out


def _scripts_de_guias(contenido: Path) -> set[str]:
    nombres = {I.XS_COMUN}
    nombres |= {g["archivo_xs"] for g in cargar_guias(contenido / "guias").values() if g.get("archivo_xs")}
    cat = K.cargar_copia(contenido)
    if cat:
        nombres |= {e.datos["archivo_xs"] for e in cat.de("guia")}
    return {n for n in nombres if Path(n).name == n}


def quitar_del_juego(perfiles: list[Path], contenido: Path = rutas.CONTENIDO) -> list[str]:
    """Quita de cada perfil lo que puso AoE2C. Devuelve los errores (vacío si todo fue bien)."""
    errores = []
    scripts = _scripts_de_guias(contenido)
    for perfil in perfiles:
        perfil = Path(perfil)
        for nombre in scripts:
            try:
                (perfil / I.XS / nombre).unlink(missing_ok=True)
            except OSError as e:
                errores.append(str(e))
        mods = [(I.NOMBRE_MOD, I.INFO_MOD["Title"])] + _mods_de_aoe2c(contenido, perfil)
        local = perfil / "mods" / "local"
        for carpeta, _titulo in mods:
            try:
                shutil.rmtree(local / carpeta)
            except FileNotFoundError:
                pass
            except OSError as e:
                errores.append(str(e))
        archivo = perfil / "mods" / I.MOD_STATUS
        if archivo.exists():
            error = I.cambiar_mod_status(archivo, [{"accion": "quitar", "carpeta": c, "titulo": t} for c, t in mods])
            if error:
                errores.append(error)
    return errores


def borrar_datos(datos: Path = rutas.DATOS) -> str | None:
    for h in list(log.handlers):  # el log está dentro: soltarlo antes de borrar
        h.close()
        log.removeHandler(h)
    try:
        shutil.rmtree(datos)
    except FileNotFoundError:
        pass
    except OSError as e:
        return str(e)
    return None


def main(args: list[str], juego_abierto=I.juego_abierto, perfiles: list[Path] | None = None,
         contenido: Path = rutas.CONTENIDO, datos: Path = rutas.DATOS, inicio=I.poner_inicio_con_windows) -> int:
    codigo = BIEN
    if "--juego" in args:
        if juego_abierto():
            return JUEGO_ABIERTO  # antes de tocar nada: el desinstalador pide cerrar el juego
        if perfiles is None:
            perfiles = [p.carpeta for p in rutas.buscar_perfiles()]
        errores = quitar_del_juego(perfiles, contenido)
        for e in errores:
            log.warning("desinstalar: %s", e)
        codigo = FALLO if errores else codigo
    if inicio(False):
        codigo = FALLO
    if "--datos" in args and borrar_datos(datos):
        codigo = FALLO
    return codigo


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
