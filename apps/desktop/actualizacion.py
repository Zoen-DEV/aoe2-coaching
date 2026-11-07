"""Actualizar AoE2C con un clic desde GitHub Releases.

Cada versión de la app se publica con la etiqueta desktop-v<versión> (por ejemplo
desktop-v1.1.0) y trae el instalador AoE2Coaching-Setup-<versión>.exe. Al abrir el panel,
la app busca la versión más nueva; si es posterior a la suya, el panel ofrece
actualizar. Al pulsar:

1. descarga el instalador en %TEMP% y comprueba su tamaño y, si GitHub lo da, su SHA-256;
2. lo abre en modo silencioso (/SILENT): el instalador cierra AoE2C, pone la versión
   nueva encima (mismas carpetas, mismos datos) y la vuelve a abrir.

Desde el código no se busca nada (la variable AOE2C_ACTUALIZAR=1 lo fuerza, para probar).
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import catalogo as K
from version import VERSION

API_RELEASES = K.API_RELEASES
PREFIJO_ETIQUETA = "desktop-v"
RE_INSTALADOR = re.compile(r"AoE2Coaching-Setup-(\d+(?:\.\d+){0,3})\.exe")
MAX_RESPUESTA = 2 * 1024 * 1024
MAX_INSTALADOR = 300 * 1024 * 1024
# Opciones de Inno Setup: sin preguntas, sin reiniciar Windows y sin la pantalla de "¿instalar?".
OPCIONES_SILENCIO = ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"]


class ActualizacionError(Exception):
    pass


@dataclass(frozen=True)
class Actualizacion:
    version: str
    url: str          # el instalador
    tamano: int
    sha256: str | None  # None si GitHub no lo da
    pagina: str       # la publicación en GitHub (novedades)


def buscar_activa() -> bool:
    """Solo la app instalada busca actualizaciones (o si se pide para probar)."""
    return bool(getattr(sys, "frozen", False)) or os.environ.get("AOE2C_ACTUALIZAR") == "1"


def elegir(publicaciones, version_app: str = VERSION) -> Actualizacion | None:
    """La versión más nueva de las publicaciones de GitHub, si es posterior a version_app."""
    mejor: Actualizacion | None = None
    for p in publicaciones if isinstance(publicaciones, list) else []:
        if not isinstance(p, dict) or p.get("draft") or p.get("prerelease"):
            continue
        etiqueta = str(p.get("tag_name", ""))
        if not etiqueta.startswith(PREFIJO_ETIQUETA):
            continue
        version = etiqueta[len(PREFIJO_ETIQUETA):]
        try:
            if not K.mas_nueva(version, version_app) or (mejor and not K.mas_nueva(version, mejor.version)):
                continue
        except K.CatalogoError:
            continue
        for a in p.get("assets") or []:
            if not isinstance(a, dict):
                continue
            m = RE_INSTALADOR.fullmatch(str(a.get("name", "")))
            url = str(a.get("browser_download_url", ""))
            tamano = a.get("size")
            if not m or m.group(1) != version or not url.startswith("https://") \
                    or not isinstance(tamano, int) or not 0 < tamano <= MAX_INSTALADOR:
                continue
            digest = str(a.get("digest") or "")
            sha = digest.removeprefix("sha256:") if digest.startswith("sha256:") else None
            if sha is not None and not K.RE_SHA256.fullmatch(sha):
                sha = None
            mejor = Actualizacion(version, url, tamano, sha, str(p.get("html_url") or ""))
            break
    return mejor


def buscar(version_app: str = VERSION, url: str = API_RELEASES) -> Actualizacion | None:
    """La actualización disponible, o None si la app está al día. Lanza ActualizacionError
    si no se puede consultar GitHub."""
    try:
        publicaciones = json.loads(K._leer(url, MAX_RESPUESTA))
    except K.CatalogoError as e:
        raise ActualizacionError(str(e)) from None
    except ValueError:
        raise ActualizacionError("GitHub devolvió una respuesta que no se entiende") from None
    return elegir(publicaciones, version_app)


def descargar(a: Actualizacion, carpeta: Path | None = None, progreso=None) -> Path:
    """Descarga el instalador y comprueba tamaño y hash. progreso(bajado, total) se llama
    de vez en cuando (desde este hilo). Si algo no cuadra, lo borra y lanza ActualizacionError."""
    carpeta = Path(carpeta) if carpeta else Path(tempfile.gettempdir()) / "AoE2Coaching"
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"AoE2Coaching-Setup-{a.version}.exe"
    parcial = destino.with_name(destino.name + ".part")
    h, total = hashlib.sha256(), 0
    try:
        with (K._pedir(a.url) if K.es_url(a.url) else open(a.url, "rb")) as origen, open(parcial, "wb") as f:
            for trozo in iter(lambda: origen.read(1 << 16), b""):
                total += len(trozo)
                if total > a.tamano:
                    break
                h.update(trozo)
                f.write(trozo)
                if progreso:
                    progreso(total, a.tamano)
    except OSError as e:
        parcial.unlink(missing_ok=True)
        raise ActualizacionError(f"no se pudo descargar la versión {a.version}: "
                                 f"{getattr(e, 'reason', None) or e}") from None
    if total != a.tamano or (a.sha256 and h.hexdigest() != a.sha256):
        parcial.unlink(missing_ok=True)
        raise ActualizacionError("el instalador llegó dañado o no es el publicado (no coincide su hash)")
    os.replace(parcial, destino)
    return destino


def lanzar(instalador: Path) -> None:
    """Abre el instalador en modo silencioso, separado de AoE2C (que después se cierra)."""
    banderas = 0
    if sys.platform == "win32":
        banderas = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(instalador), *OPCIONES_SILENCIO], close_fds=True, creationflags=banderas)
