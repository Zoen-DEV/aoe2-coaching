"""Instala en el juego lo que se elige en el panel: guías, mapas y mods del catálogo.

- **Guías.** Llegan en un paquete del catálogo (manifiesto del overlay + script .xs) y se
  guardan en %APPDATA%\\AoE2Coaching\\contenido\\guias. Todos los mapas [AoE2C] cargan el
  mismo script, aoe2c_guia.xs, de la carpeta xs del perfil: elegir una guía es copiar su
  script encima de ese archivo. Vale para la siguiente partida, sin reiniciar el juego.
- **Mapas.** Se arman aquí con el .rms oficial del juego (mapas.py) dentro del mod local
  "guia-apertura-castillos". Si el juego actualiza el mapa oficial, el instalado deja de
  coincidir y reparar_mapas() lo vuelve a armar. Un mapa nuevo sale al reiniciar el juego.
- **Mods.** Llegan en un paquete y se copian a mods\\local\\<carpeta> del perfil.
- **mod-status.json.** La lista de mods del juego (no documentada). AoE2C activa ahí sus
  mods solo con el juego cerrado (si está abierto, queda pendiente hasta que se cierre),
  guarda antes una copia del archivo y solo toca sus propias líneas.
"""

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import catalogo as K
import mapas as M
import rutas
from lector import cargar_guias

HERE = Path(__file__).resolve().parent
NOMBRE_MOD = "guia-apertura-castillos"  # el mod local que lleva los mapas [AoE2C]
INFO_MOD = {
    "Title": "AoE2 Coaching",
    "Description": (
        "Mapas con una guía paso a paso de la apertura (Fast Castle, Scouts...). La guía se elige en el "
        "panel de AoE2C. Cada paso se marca solo al cumplirse y te dice si vas adelantado o tarde. "
        "En la sala elige Estilo de mapa: Personalizado y un mapa \"[AoE2C] ...\"."
    ),
    "Author": "enzoholgadodev",
}
XS_COMUN = M.XS_COMUN
RMS = Path("resources") / "_common" / "random-map-scripts"
XS = Path("resources") / "_common" / "xs"
MOD_STATUS = "mod-status.json"
COPIA_MOD_STATUS = "mod-status.json.aoe2c.bak"
ID_STEAM_JUEGO = 813780
SIN_PERFIL = "no se encontró la carpeta del perfil del juego (abre el juego una vez)"
JUEGO_ABIERTO = "cierra el juego primero"
CLAVE_INICIO = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOMBRE_INICIO = "AoE2Coaching"


@dataclass
class EstadoMapa:
    mapa: dict
    estado: str  # instalado, desactualizado, no_instalado, sin_juego (falta el oficial) o necesita_app
    imagen: Path | None


@dataclass
class EstadoMod:
    elemento: K.Elemento
    estado: str              # instalado, desactualizado, no_instalado o necesita_app
    version: str | None      # la instalada (None si no se sabe)
    activacion: str          # activo, desactivado, sin_registrar o pendiente (en mod-status.json)


def mismos_bytes(a: Path, b: Path) -> bool:
    try:
        return a.stat().st_size == b.stat().st_size and a.read_bytes() == b.read_bytes()
    except OSError:
        return False


def _clave(perfil: Path) -> str:
    return os.path.normcase(str(perfil))


def _escribir(ruta: Path, datos: bytes) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_bytes(datos)
    os.replace(tmp, ruta)


class Instalador:
    """Las carpetas del perfil y del juego las da rutas.py; pueden faltar (None) si el
    juego no está instalado o no se abrió nunca. `catalogo` lo pone el panel."""

    def __init__(self, perfil: Path | None = None, juego: Path | None = None, contenido: Path | None = None,
                 catalogo: K.Catalogo | None = None):
        self.perfil = Path(perfil) if perfil else None
        self.juego = Path(juego) if juego else None
        self.contenido = Path(contenido) if contenido else rutas.CONTENIDO
        self.catalogo = catalogo

    # --- Rutas ---
    @property
    def carpeta_guias(self) -> Path:
        return self.contenido / "guias"

    @property
    def descargas(self) -> Path:
        return self.contenido / "descargas"

    @property
    def xs_perfil(self) -> Path | None:
        return self.perfil / XS if self.perfil else None

    @property
    def mods_locales(self) -> Path | None:
        return self.perfil / "mods" / "local" if self.perfil else None

    @property
    def mod_instalado(self) -> Path | None:
        return self.mods_locales / NOMBRE_MOD if self.perfil else None

    @property
    def mod_status(self) -> Path | None:
        return self.perfil / "mods" / MOD_STATUS if self.perfil else None

    def juego_instalado(self) -> bool:
        return rutas.es_carpeta_juego(self.juego)

    # --- Estado guardado (contenido/instalado.json) ---
    # {"guias": {id: versión}, "mods": {perfil: {id: versión}}, "pendientes": [{perfil, accion, carpeta, titulo}]}
    @property
    def _archivo_estado(self) -> Path:
        return self.contenido / "instalado.json"

    def _estado(self) -> dict:
        try:
            d = json.loads(self._archivo_estado.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        d = d if isinstance(d, dict) else {}
        for clave, vacio in (("guias", {}), ("mods", {}), ("pendientes", [])):
            if not isinstance(d.get(clave), type(vacio)):
                d[clave] = vacio
        return d

    def _guardar_estado(self, d: dict) -> None:
        try:
            _escribir(self._archivo_estado, json.dumps(d, ensure_ascii=False, indent=1).encode("utf-8"))
        except OSError:
            pass

    # --- Guías ---
    def guias(self) -> dict[str, dict]:
        """Las guías instaladas en la app (manifiestos), por id."""
        return cargar_guias(self.carpeta_guias)

    def version_guia(self, id_: str) -> str | None:
        return self._estado()["guias"].get(id_)

    def instalar_guia(self, e: K.Elemento, paquete: Path) -> str | None:
        """Instala (o actualiza) una guía con su paquete ya descargado y comprobado."""
        tmp = self.contenido / f".nueva-{e.id}"
        try:
            shutil.rmtree(tmp, ignore_errors=True)
            archivos = {p.name: p for p in K.extraer(paquete, tmp)}
            xs = e.datos["archivo_xs"]
            nombre_manifiesto = Path(xs).stem + ".json"
            if set(archivos) != {xs, nombre_manifiesto}:
                return f"el paquete de {e.id} no trae {xs} y {nombre_manifiesto}"
            try:
                manifiesto = json.loads(archivos[nombre_manifiesto].read_text(encoding="utf-8"))
            except ValueError:
                return f"el manifiesto de {e.id} no es JSON válido"
            if manifiesto.get("id") != e.id or manifiesto.get("archivo_xs") != xs or not manifiesto.get("pasos"):
                return f"el paquete no corresponde a la guía {e.id}"
            self.carpeta_guias.mkdir(parents=True, exist_ok=True)
            os.replace(archivos[xs], self.carpeta_guias / xs)  # el script primero: el manifiesto la "publica"
            os.replace(archivos[nombre_manifiesto], self.carpeta_guias / nombre_manifiesto)
        except (OSError, K.CatalogoError) as error:
            return str(error)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        d = self._estado()
        d["guias"][e.id] = e.version
        self._guardar_estado(d)
        return None

    def quitar_guia(self, guia: dict) -> str | None:
        """Borra la guía de la app (no toca el aoe2c_guia.xs del perfil)."""
        try:
            for nombre in (guia["archivo_xs"], Path(guia["archivo_xs"]).stem + ".json"):
                (self.carpeta_guias / nombre).unlink(missing_ok=True)
        except OSError as error:
            return str(error)
        d = self._estado()
        d["guias"].pop(guia["id"], None)
        self._guardar_estado(d)
        return None

    def guia_instalada(self, guias: dict[str, dict]) -> str | None:
        """Id de la guía que cargan ahora los mapas (según el aoe2c_guia.xs del perfil)."""
        if self.perfil is None:
            return None
        actual = self.xs_perfil / XS_COMUN
        for id_, guia in guias.items():
            if mismos_bytes(actual, self.carpeta_guias / guia["archivo_xs"]):
                return id_
        return None

    def activar_guia(self, guia: dict) -> str | None:
        """Copia el script de la guía como aoe2c_guia.xs. Devuelve un error o None."""
        if self.perfil is None:
            return SIN_PERFIL
        origen = self.carpeta_guias / guia["archivo_xs"]
        if not origen.is_file():
            return f"falta {origen.name}: vuelve a instalar la guía"
        try:
            for destino in (self.xs_perfil, self.mod_instalado / XS):
                destino.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origen, destino / guia["archivo_xs"])
                tmp = destino / (XS_COMUN + ".tmp")
                shutil.copy2(origen, tmp)
                os.replace(tmp, destino / XS_COMUN)
        except OSError as e:
            return str(e)
        return None

    # --- Mapas ---
    def mapas(self) -> list[dict]:
        """Las recetas de los mapas del catálogo."""
        if self.catalogo is None:
            return []
        return [{"id": e.id, "nombre": e.nombre["es"], "nombres": e.nombre, "descripcion": e.descripcion,
                 "version": e.version, "compatible": e.compatible(), **e.datos} for e in self.catalogo.de("mapa")]

    def _rms_instalado(self, mapa: dict) -> Path | None:
        return self.mod_instalado / RMS / mapa["archivo"] if self.perfil else None

    def _vista_previa(self, mapa: dict) -> Path | None:
        """Imagen para la tarjeta del panel: la del mapa instalado o, si no, una armada
        con la imagen oficial y guardada en contenido/imagenes."""
        instalado = self._rms_instalado(mapa)
        if instalado is not None and instalado.with_suffix(".png").is_file():
            return instalado.with_suffix(".png")
        destino = self.contenido / "imagenes" / (Path(mapa["archivo"]).stem + ".png")
        if destino.is_file():
            return destino
        oficial = M.imagen_oficial(self.juego, mapa)
        if oficial is None:
            return None
        try:
            M.armar_imagen(oficial, destino)
        except (M.MapaError, OSError):
            return None
        return destino

    def estado_mapas(self) -> list[EstadoMapa]:
        out = []
        for m in self.mapas():
            instalado = self._rms_instalado(m)
            try:
                esperado = M.armar_rms(self.juego, m)
            except M.MapaError:
                esperado = None
            if instalado is None or not instalado.is_file():
                estado = "necesita_app" if not m["compatible"] else "no_instalado" if esperado else "sin_juego"
            elif esperado is None:
                estado = "instalado"  # sin el oficial no se puede comprobar
            else:
                try:
                    estado = "instalado" if instalado.read_bytes() == esperado else "desactualizado"
                except OSError:
                    estado = "desactualizado"
            out.append(EstadoMapa(m, estado, self._vista_previa(m)))
        return out

    def reparar_mapas(self) -> list[str]:
        """Vuelve a armar los mapas instalados que ya no coinciden con su versión actual
        (el juego actualizó el oficial o cambió la receta). Devuelve sus nombres."""
        return [em.mapa["nombre"] for em in self.estado_mapas()
                if em.estado == "desactualizado" and em.mapa["compatible"] and self.instalar_mapa(em.mapa) is None]

    def instalar_mapa(self, mapa: dict, guia: dict | None = None) -> str | None:
        """Arma el mapa (y su imagen) en el mod local. Si el perfil aún no tiene el script
        común, instala también el de la guía `guia`."""
        if self.perfil is None:
            return SIN_PERFIL
        try:
            datos = M.armar_rms(self.juego, mapa)
            destino = self.mod_instalado / RMS / mapa["archivo"]
            _escribir(destino, datos)
            oficial = M.imagen_oficial(self.juego, mapa)
            if oficial is not None:
                M.armar_imagen(oficial, destino.with_suffix(".png"))
            info = self.mod_instalado / "info.json"
            if not info.is_file():
                _escribir(info, (json.dumps(INFO_MOD, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        except (M.MapaError, OSError) as e:
            return str(e)
        if self.activacion(NOMBRE_MOD) != "activo":
            self._pendiente("activar", NOMBRE_MOD, INFO_MOD["Title"])
        if guia and not (self.xs_perfil / XS_COMUN).is_file():
            return self.activar_guia(guia)
        return None

    def quitar_mapa(self, mapa: dict) -> str | None:
        if self.perfil is None:
            return SIN_PERFIL
        instalado = self._rms_instalado(mapa)
        try:
            for p in (instalado, instalado.with_suffix(".png")):
                if p.is_file():
                    p.unlink()
        except OSError as e:
            return str(e)
        return None

    def exportar_mapa(self, mapa: dict, carpeta: Path) -> str | None:
        """Guarda una copia del .rms (y su imagen) en otra carpeta."""
        try:
            destino = Path(carpeta) / mapa["archivo"]
            _escribir(destino, M.armar_rms(self.juego, mapa))
            oficial = M.imagen_oficial(self.juego, mapa)
            if oficial is not None:
                M.armar_imagen(oficial, destino.with_suffix(".png"))
        except (M.MapaError, OSError) as e:
            return str(e)
        return None

    # --- Mods ---
    def _mods_perfil(self, d: dict) -> dict:
        return d["mods"].setdefault(_clave(self.perfil), {}) if self.perfil else {}

    def estado_mods(self) -> list[EstadoMod]:
        if self.catalogo is None:
            return []
        versiones = self._mods_perfil(self._estado())
        out = []
        for e in self.catalogo.de("mod"):
            carpeta = self.mods_locales / e.datos["carpeta"] if self.perfil else None
            version = versiones.get(e.id)
            if carpeta is None or not (carpeta / "info.json").is_file():
                estado, version = ("no_instalado" if e.compatible() else "necesita_app"), None
            elif version and not K.mas_nueva(e.version, version):
                estado = "instalado"
            else:
                estado = "desactualizado"  # versión vieja, o instalado a mano (sin versión conocida)
            out.append(EstadoMod(e, estado, version, self.activacion(e.datos["carpeta"])))
        return out

    def instalar_mod(self, e: K.Elemento, paquete: Path, juego_abierto: bool = False) -> str | None:
        """Copia el mod a mods\\local\\<carpeta> (lo sustituye si ya estaba) y deja su
        activación pendiente hasta que el juego esté cerrado."""
        if self.perfil is None:
            return SIN_PERFIL
        carpeta = self.mods_locales / e.datos["carpeta"]
        if juego_abierto and carpeta.exists():
            return JUEGO_ABIERTO  # el juego tiene cargados sus archivos
        nueva = self.mods_locales / f".aoe2c-{e.datos['carpeta']}-nuevo"
        vieja = self.mods_locales / f".aoe2c-{e.datos['carpeta']}-viejo"
        try:
            for tmp in (nueva, vieja):
                shutil.rmtree(tmp, ignore_errors=True)
            K.extraer(paquete, nueva)
            if not (nueva / "info.json").is_file():
                return f"el paquete de {e.id} no es un mod (le falta info.json)"
            if carpeta.exists():
                os.replace(carpeta, vieja)
            os.replace(nueva, carpeta)
        except (OSError, K.CatalogoError) as error:
            if vieja.exists() and not carpeta.exists():
                os.replace(vieja, carpeta)  # deja el mod como estaba
            return str(error)
        finally:
            shutil.rmtree(nueva, ignore_errors=True)
            shutil.rmtree(vieja, ignore_errors=True)
        d = self._estado()
        self._mods_perfil(d)[e.id] = e.version
        self._guardar_estado(d)
        if self.activacion(e.datos["carpeta"]) != "activo":
            self._pendiente("activar", e.datos["carpeta"], e.datos["titulo"])
        return None

    def quitar_mod(self, e: K.Elemento, juego_abierto: bool = False) -> str | None:
        """Borra la carpeta del mod y su línea de mod-status.json (con el juego cerrado)."""
        if self.perfil is None:
            return SIN_PERFIL
        if juego_abierto:
            return JUEGO_ABIERTO
        try:
            shutil.rmtree(self.mods_locales / e.datos["carpeta"])
        except FileNotFoundError:
            pass
        except OSError as error:
            return str(error)
        d = self._estado()
        self._mods_perfil(d).pop(e.id, None)
        self._guardar_estado(d)
        self._pendiente("quitar", e.datos["carpeta"], e.datos["titulo"])
        return self.aplicar_pendientes(False)[1]

    # --- mod-status.json ---
    def pendientes(self) -> list[dict]:
        if self.perfil is None:
            return []
        return [p for p in self._estado()["pendientes"] if p.get("perfil") == _clave(self.perfil)]

    def _pendiente(self, accion: str, carpeta: str, titulo: str) -> None:
        d = self._estado()
        perfil = _clave(self.perfil)
        d["pendientes"] = [p for p in d["pendientes"] if not (p.get("perfil") == perfil and p.get("carpeta") == carpeta)]
        d["pendientes"].append({"perfil": perfil, "accion": accion, "carpeta": carpeta, "titulo": titulo})
        self._guardar_estado(d)

    def activacion(self, carpeta: str) -> str:
        """activo, desactivado o sin_registrar según mod-status.json; pendiente si AoE2C
        espera a que se cierre el juego para activarlo."""
        if any(p["carpeta"] == carpeta and p["accion"] == "activar" for p in self.pendientes()):
            return "pendiente"
        entrada = buscar_en_mod_status(self.mod_status, carpeta) if self.perfil else None
        if entrada is None:
            return "sin_registrar"
        return "activo" if entrada.get("Enabled") else "desactivado"

    def activar_mod(self, carpeta: str, titulo: str, juego_abierto: bool = False) -> tuple[list[dict], str | None]:
        """Pide activar un mod que el jugador desactivó en el juego."""
        if self.perfil is None:
            return [], SIN_PERFIL
        self._pendiente("activar", carpeta, titulo)
        return self.aplicar_pendientes(juego_abierto)

    def aplicar_pendientes(self, juego_abierto: bool) -> tuple[list[dict], str | None]:
        """Con el juego cerrado, aplica en mod-status.json lo pendiente de este perfil.
        Devuelve (lo aplicado, error). Si falla, lo pendiente se descarta y el error
        se muestra con cómo hacerlo a mano."""
        pendientes = self.pendientes()
        if juego_abierto or not pendientes:
            return [], None
        error = cambiar_mod_status(self.mod_status, pendientes)
        d = self._estado()
        d["pendientes"] = [p for p in d["pendientes"] if p not in pendientes]
        self._guardar_estado(d)
        return (pendientes if error is None else []), error


def _ruta_mod(carpeta: str) -> str:
    return f"local//{carpeta}"


def _leer_mod_status(archivo: Path) -> dict | None:
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(datos, dict) or not isinstance(datos.get("Mods"), list):
        return None
    return datos


def buscar_en_mod_status(archivo: Path, carpeta: str) -> dict | None:
    datos = _leer_mod_status(archivo)
    for m in (datos or {}).get("Mods", []):
        if isinstance(m, dict) and str(m.get("Path", "")).lower() == _ruta_mod(carpeta).lower():
            return m
    return None


def cambiar_mod_status(archivo: Path, cambios: list[dict]) -> str | None:
    """Activa o quita mods locales en mod-status.json. Solo toca sus líneas: las demás
    quedan igual y en el mismo orden (un mod nuevo va al final, con la prioridad más
    baja). Antes guarda una copia (mod-status.json.aoe2c.bak). Llamar con el juego
    cerrado: si está abierto, lo pisa al salir."""
    archivo = Path(archivo)
    if archivo.exists():
        datos = _leer_mod_status(archivo)
        if datos is None:
            return f"{archivo.name} tiene un formato que AoE2C no reconoce"
    else:
        datos = {"Mods": [], "Unsub": []}  # el juego aún no lo creó (perfil sin mods)
    mods = datos["Mods"]
    cambiado = False
    for c in cambios:
        ruta = _ruta_mod(c["carpeta"]).lower()
        mias = [m for m in mods if isinstance(m, dict) and str(m.get("Path", "")).lower() == ruta]
        if c["accion"] == "quitar":
            if mias:
                mods[:] = [m for m in mods if not any(m is x for x in mias)]
                cambiado = True
        elif mias:
            for m in mias:
                if m.get("Enabled") is not True:
                    m["Enabled"] = True
                    cambiado = True
        else:
            prioridades = [m.get("Priority") for m in mods if isinstance(m, dict) and isinstance(m.get("Priority"), int)]
            mods.append({"CheckSum": "0", "Enabled": True, "LastUpdate": "0", "Path": _ruta_mod(c["carpeta"]),
                         "Priority": max(prioridades, default=0) + 1, "PublishID": 0, "Title": c["titulo"],
                         "WorkshopID": 0})
            cambiado = True
    if not cambiado:
        return None
    try:
        if archivo.exists():
            shutil.copy2(archivo, archivo.with_name(COPIA_MOD_STATUS))
        _escribir(archivo, json.dumps(datos, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
    except OSError as e:
        return str(e)
    return None


# --- Juego y Windows ----------------------------------------------------------


def juego_abierto() -> bool:
    """True si AoE2DE_s.exe se está ejecutando (lista de procesos de Windows)."""
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                        ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        foto = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
        if not foto or foto == wintypes.HANDLE(-1).value:
            return False
        try:
            e = PROCESSENTRY32W()
            e.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = kernel32.Process32FirstW(foto, ctypes.byref(e))
            while ok:
                if e.szExeFile.lower() == "aoe2de_s.exe":
                    return True
                ok = kernel32.Process32NextW(foto, ctypes.byref(e))
        finally:
            kernel32.CloseHandle(foto)
    except (OSError, AttributeError):
        pass
    return False


def abrir_juego() -> None:
    """Abre AoE2 DE con Steam."""
    os.startfile(f"steam://rungameid/{ID_STEAM_JUEGO}")


def abrir_enlace(url: str) -> None:
    if url.startswith("https://"):
        os.startfile(url)


def abrir_carpeta(carpeta: Path) -> None:
    if Path(carpeta).exists():
        os.startfile(str(carpeta))


def comando_inicio() -> str:
    """Orden que abre AoE2C al iniciar sesión: el .exe empaquetado o, desde el código,
    pythonw + aoe2c.py. --inicio hace que espere en la bandeja sin abrir el panel."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --inicio'
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    return f'"{pyw if pyw.is_file() else exe}" "{HERE / "aoe2c.py"}" --inicio'


def actualizar_inicio_con_windows() -> bool:
    """Si el inicio con Windows está activo pero apunta a otra orden (otra carpeta o una
    versión anterior), lo corrige. Devuelve True si lo cambió."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_INICIO) as k:
            actual = winreg.QueryValueEx(k, NOMBRE_INICIO)[0]
    except OSError:
        return False
    if actual == comando_inicio():
        return False
    return poner_inicio_con_windows(True) is None


def inicio_con_windows() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_INICIO) as k:
            winreg.QueryValueEx(k, NOMBRE_INICIO)
        return True
    except OSError:
        return False


def poner_inicio_con_windows(activo: bool) -> str | None:
    """Añade o quita AoE2C de los programas que se abren al iniciar sesión (solo este usuario)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_INICIO, 0, winreg.KEY_SET_VALUE) as k:
            if activo:
                winreg.SetValueEx(k, NOMBRE_INICIO, 0, winreg.REG_SZ, comando_inicio())
            else:
                try:
                    winreg.DeleteValue(k, NOMBRE_INICIO)
                except FileNotFoundError:
                    pass
    except OSError as e:
        return str(e)
    return None
