"""Catálogo de contenido: las guías, los mapas y los mods que se instalan desde el panel.

Se publica en GitHub Releases (etiquetas contenido-*) como catalogo.json, junto a los
paquetes .zip de las guías y los mods. Lo genera content/catalogo.py. Formato 1:

    {
      "formato": 1,
      "generado": "2026-11-07T18:00:00Z",
      "elementos": [
        {
          "tipo": "guia",                 # guia, mapa o mod
          "id": "fast_castle",
          "version": "1.0.0",
          "app_minima": "1.0.0",          # versión de la app que hace falta para instalarlo
          "nombre": {"es": "...", "en": "..."},
          "descripcion": {"es": "...", "en": "..."},
          "paquete": {"archivo": "guia-fast_castle-1.0.0.zip", "sha256": "...", "tamano": 12345},
          "datos": {...}                  # lo propio de cada tipo (ver DATOS)
        }
      ]
    }

- Las guías y los mods traen un paquete; "archivo" es relativo al catalogo.json (o una URL).
  La app lo descarga y comprueba su tamaño y su SHA-256 antes de usarlo.
- Los mapas no traen paquete: son una "receta" (mapa oficial, nombre, imagen) y la app
  los arma con el .rms oficial del juego del usuario (ver mapas.py).
- Una app vieja ignora los tipos que no conoce y no instala lo que pide una app_minima
  mayor que la suya ("Necesita actualizar la app").
"""

import hashlib
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from version import VERSION

FORMATO = 1
TIPOS = ("guia", "mapa", "mod")
REPO = "Zoen-DEV/aoe2-coaching"
API_RELEASES = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
PREFIJO_ETIQUETA = "contenido-"
NOMBRE = "catalogo.json"
GITHUB = "github"  # fuente: el último catálogo publicado en GitHub Releases
TIEMPO_ESPERA = 20  # segundos por conexión
MAX_CATALOGO = 2 * 1024 * 1024
MAX_PAQUETE = 200 * 1024 * 1024
RAIZ = Path(__file__).resolve().parent.parent.parent  # raíz del monorepo (al ejecutar desde el código)

RE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
RE_VERSION = re.compile(r"\d{1,6}(\.\d{1,6}){0,3}")
RE_SHA256 = re.compile(r"[0-9a-f]{64}")
# Lo que lleva "datos" según el tipo: clave -> expresión que debe cumplir (None = texto por idioma o lista).
DATOS = {
    "guia": {"archivo_xs": re.compile(r"guia_[a-z0-9_]+\.xs"), "nivel": re.compile(r"facil|media|dificil"),
             "mapas_recomendados": None},
    "mapa": {"base": re.compile(r"[A-Za-z0-9_ -]+\.rms"), "archivo": re.compile(r"\[AoE2C\] [A-Za-z0-9 _()-]+\.rms"),
             "tipo": None, "guias": None},
    "mod": {"carpeta": RE_ID, "titulo": re.compile(r"[^\x00-\x1f]{1,120}")},
}
DATOS_OPCIONALES = {"mapa": {"imagen": re.compile(r"[A-Za-z0-9_.-]+\.png")}}
CON_PAQUETE = ("guia", "mod")


class CatalogoError(Exception):
    pass


# --- Versiones ----------------------------------------------------------------------


def version_tupla(v: str) -> tuple[int, ...]:
    if not isinstance(v, str) or not RE_VERSION.fullmatch(v):
        raise CatalogoError(f"versión no válida: {v!r} (se espera algo como 1.2.0)")
    partes = tuple(int(x) for x in v.split("."))
    return partes + (0,) * (4 - len(partes))


def mas_nueva(a: str, b: str) -> bool:
    """True si la versión a es posterior a la b."""
    return version_tupla(a) > version_tupla(b)


# --- Formato ------------------------------------------------------------------------


@dataclass(frozen=True)
class Paquete:
    archivo: str
    sha256: str
    tamano: int


@dataclass
class Elemento:
    tipo: str
    id: str
    version: str
    app_minima: str
    nombre: dict
    descripcion: dict
    datos: dict
    paquete: Paquete | None = None

    def texto(self, campo: str, idioma: str) -> str:
        valor = getattr(self, campo) if campo in ("nombre", "descripcion") else self.datos.get(campo) or {}
        return valor.get(idioma) or valor.get("es") or ""

    def compatible(self, version_app: str = VERSION) -> bool:
        return not mas_nueva(self.app_minima, version_app)

    def a_dict(self) -> dict:
        d = {"tipo": self.tipo, "id": self.id, "version": self.version, "app_minima": self.app_minima,
             "nombre": self.nombre, "descripcion": self.descripcion}
        if self.paquete:
            d["paquete"] = {"archivo": self.paquete.archivo, "sha256": self.paquete.sha256, "tamano": self.paquete.tamano}
        d["datos"] = self.datos
        return d


@dataclass
class Catalogo:
    elementos: list[Elemento]
    origen: str = ""     # de dónde salió (URL o ruta del catalogo.json): los paquetes se buscan a su lado
    generado: str = ""
    descartados: list[str] = field(default_factory=list)  # elementos que esta versión no entiende

    def de(self, tipo: str) -> list[Elemento]:
        return [e for e in self.elementos if e.tipo == tipo]

    def buscar(self, tipo: str, id_: str) -> Elemento | None:
        return next((e for e in self.elementos if e.tipo == tipo and e.id == id_), None)

    def url_paquete(self, e: Elemento) -> str:
        archivo = e.paquete.archivo
        if es_url(archivo):
            return archivo
        if es_url(self.origen):
            return urllib.parse.urljoin(self.origen, urllib.parse.quote(archivo))
        return str(Path(self.origen).parent / archivo)


def es_url(texto: str) -> bool:
    return texto.startswith(("https://", "http://"))


def _textos(valor, donde: str) -> dict:
    if not isinstance(valor, dict) or not all(isinstance(valor.get(i), str) and valor[i].strip() for i in ("es", "en")):
        raise CatalogoError(f"{donde}: se espera un texto en español y en inglés ({{'es': ..., 'en': ...}})")
    return {"es": valor["es"], "en": valor["en"]}


def _elemento(d, n: int) -> Elemento:
    donde = f"elemento {n}"
    if not isinstance(d, dict):
        raise CatalogoError(f"{donde}: no es un objeto")
    tipo, id_ = d.get("tipo"), d.get("id")
    if not isinstance(id_, str) or not RE_ID.fullmatch(id_):
        raise CatalogoError(f"{donde}: id no válido: {id_!r}")
    donde = f"{tipo} {id_}"
    version_tupla(d.get("version"))
    version_tupla(d.get("app_minima"))
    datos = d.get("datos")
    if not isinstance(datos, dict):
        raise CatalogoError(f"{donde}: falta 'datos'")
    for clave, regla in DATOS[tipo].items():
        valor = datos.get(clave)
        if regla is not None:
            if not isinstance(valor, str) or not regla.fullmatch(valor):
                raise CatalogoError(f"{donde}: datos.{clave} no válido: {valor!r}")
        elif clave == "tipo":
            _textos(valor, f"{donde}: datos.tipo")
        elif not isinstance(valor, list) or not all(isinstance(x, str) for x in valor):
            raise CatalogoError(f"{donde}: datos.{clave} debe ser una lista de ids")
    for clave, regla in DATOS_OPCIONALES.get(tipo, {}).items():
        if clave in datos and (not isinstance(datos[clave], str) or not regla.fullmatch(datos[clave])):
            raise CatalogoError(f"{donde}: datos.{clave} no válido: {datos[clave]!r}")
    paquete = None
    if tipo in CON_PAQUETE:
        p = d.get("paquete")
        if not isinstance(p, dict):
            raise CatalogoError(f"{donde}: falta 'paquete'")
        archivo, sha, tam = p.get("archivo"), p.get("sha256"), p.get("tamano")
        if not isinstance(archivo, str) or not archivo or (not es_url(archivo) and not re.fullmatch(r"[A-Za-z0-9_.-]+", archivo)):
            raise CatalogoError(f"{donde}: paquete.archivo no válido: {archivo!r}")
        if not isinstance(sha, str) or not RE_SHA256.fullmatch(sha):
            raise CatalogoError(f"{donde}: paquete.sha256 no válido")
        if not isinstance(tam, int) or isinstance(tam, bool) or not 0 < tam <= MAX_PAQUETE:
            raise CatalogoError(f"{donde}: paquete.tamano no válido: {tam!r}")
        paquete = Paquete(archivo, sha, tam)
    return Elemento(tipo, id_, d["version"], d["app_minima"], _textos(d.get("nombre"), f"{donde}: nombre"),
                    _textos(d.get("descripcion"), f"{donde}: descripcion"), datos, paquete)


def leer(datos, origen: str = "", estricto: bool = False) -> Catalogo:
    """Lee y comprueba un catálogo (bytes, texto o diccionario). Sin `estricto`, los
    elementos que esta versión no entiende se descartan (y se anotan) en vez de fallar."""
    if isinstance(datos, (bytes, str)):
        try:
            datos = json.loads(datos)
        except ValueError as e:
            raise CatalogoError(f"el catálogo no es JSON válido: {e}") from None
    if not isinstance(datos, dict) or not isinstance(datos.get("elementos"), list):
        raise CatalogoError("al catálogo le falta la lista 'elementos'")
    formato = datos.get("formato")
    if not isinstance(formato, int) or formato < 1:
        raise CatalogoError(f"formato de catálogo no válido: {formato!r}")
    if formato > FORMATO:
        raise CatalogoError("el catálogo es de una versión más nueva de AoE2C: actualiza la app")
    elementos, descartados, vistos = [], [], set()
    for n, d in enumerate(datos["elementos"], 1):
        if isinstance(d, dict) and d.get("tipo") not in TIPOS:
            if estricto:
                raise CatalogoError(f"elemento {n}: tipo desconocido {d.get('tipo')!r}")
            descartados.append(f"elemento {n}: tipo {d.get('tipo')!r}")
            continue
        try:
            e = _elemento(d, n)
            if (e.tipo, e.id) in vistos:
                raise CatalogoError(f"{e.tipo} {e.id}: repetido")
        except CatalogoError as error:
            if estricto:
                raise
            descartados.append(str(error))
            continue
        vistos.add((e.tipo, e.id))
        elementos.append(e)
    return Catalogo(elementos, origen, str(datos.get("generado", "")), descartados)


def a_json(cat: Catalogo, generado: str) -> str:
    return json.dumps({"formato": FORMATO, "generado": generado, "elementos": [e.a_dict() for e in cat.elementos]},
                      ensure_ascii=False, indent=1) + "\n"


# --- Descargas -----------------------------------------------------------------------


def _pedir(url: str, aceptar: str = "*/*"):
    req = urllib.request.Request(url, headers={"User-Agent": f"AoE2Coaching/{VERSION}", "Accept": aceptar})
    return urllib.request.urlopen(req, timeout=TIEMPO_ESPERA)


def _leer(fuente: str, maximo: int) -> bytes:
    try:
        if es_url(fuente):
            with _pedir(fuente) as r:
                datos = r.read(maximo + 1)
        else:
            with open(fuente, "rb") as f:
                datos = f.read(maximo + 1)
    except OSError as e:  # incluye los errores de red (URLError) y HTTP
        raise CatalogoError(f"no se pudo leer {fuente}: {getattr(e, 'reason', None) or e}") from None
    if len(datos) > maximo:
        raise CatalogoError(f"{fuente} es demasiado grande")
    return datos


def url_github() -> str:
    """URL del catalogo.json de la última publicación de contenido (etiqueta contenido-*)."""
    try:
        publicaciones = json.loads(_leer(API_RELEASES, MAX_CATALOGO))
    except ValueError:
        raise CatalogoError("GitHub devolvió una respuesta que no se entiende") from None
    for p in publicaciones if isinstance(publicaciones, list) else []:
        if p.get("draft") or p.get("prerelease") or not str(p.get("tag_name", "")).startswith(PREFIJO_ETIQUETA):
            continue
        for a in p.get("assets") or []:
            if a.get("name") == NOMBRE and es_url(str(a.get("browser_download_url", ""))):
                return a["browser_download_url"]
    raise CatalogoError("todavía no hay ningún catálogo publicado")


def fuente_por_defecto() -> str:
    """De dónde se lee el catálogo: la variable AOE2C_CATALOGO (URL o ruta); al ejecutar
    desde el código, el que genera content/catalogo.py en build/catalogo si existe; si
    no, GitHub Releases."""
    propia = os.environ.get("AOE2C_CATALOGO")
    if propia:
        return propia
    local = RAIZ / "build" / "catalogo" / NOMBRE
    if not getattr(sys, "frozen", False) and local.is_file():
        return str(local)
    return GITHUB


def descargar(fuente: str = GITHUB) -> tuple[Catalogo, bytes]:
    """(catálogo, bytes del catalogo.json). Lanza CatalogoError si no se puede."""
    url = url_github() if fuente == GITHUB else fuente
    datos = _leer(url, MAX_CATALOGO)
    return leer(datos, url), datos


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 16), b""):
            h.update(trozo)
    return h.hexdigest()


def descargar_paquete(cat: Catalogo, e: Elemento, carpeta: Path) -> Path:
    """Descarga el paquete de `e` en `carpeta` y comprueba su tamaño y su SHA-256.
    Si algo no cuadra, lo borra y lanza CatalogoError."""
    if e.paquete is None:
        raise CatalogoError(f"{e.id} no tiene paquete")
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{e.tipo}-{e.id}-{e.version}.zip"
    parcial = destino.with_name(destino.name + ".part")
    url = cat.url_paquete(e)
    h, total = hashlib.sha256(), 0
    try:
        with (_pedir(url) if es_url(url) else open(url, "rb")) as origen, open(parcial, "wb") as f:
            for trozo in iter(lambda: origen.read(1 << 16), b""):
                total += len(trozo)
                if total > e.paquete.tamano:
                    break
                h.update(trozo)
                f.write(trozo)
    except OSError as error:
        parcial.unlink(missing_ok=True)
        raise CatalogoError(f"no se pudo descargar {e.paquete.archivo}: {getattr(error, 'reason', None) or error}") from None
    if total != e.paquete.tamano or h.hexdigest() != e.paquete.sha256:
        parcial.unlink(missing_ok=True)
        raise CatalogoError(f"{e.paquete.archivo} llegó dañado o no es el publicado (no coincide su hash)")
    os.replace(parcial, destino)
    return destino


def extraer(zip_ruta: Path, destino: Path, maximo: int = MAX_PAQUETE * 4) -> list[Path]:
    """Extrae un paquete sin dejar que ningún archivo salga de `destino`."""
    destino = Path(destino)
    out = []
    try:
        with zipfile.ZipFile(zip_ruta) as z:
            miembros = [m for m in z.infolist() if not m.is_dir()]
            if sum(m.file_size for m in miembros) > maximo:
                raise CatalogoError("el paquete es demasiado grande")
            for m in miembros:
                partes = Path(m.filename.replace("\\", "/")).parts
                if not partes or m.filename.startswith(("/", "\\")) or ".." in partes or ":" in m.filename:
                    raise CatalogoError(f"el paquete tiene una ruta no permitida: {m.filename}")
                ruta = destino.joinpath(*partes)
                ruta.parent.mkdir(parents=True, exist_ok=True)
                with z.open(m) as src, open(ruta, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                out.append(ruta)
    except (OSError, zipfile.BadZipFile) as e:
        raise CatalogoError(f"no se pudo abrir el paquete: {e}") from None
    return out


# --- Copia local (para usarlo sin conexión) ------------------------------------------------


def guardar_copia(datos: bytes, origen: str, carpeta: Path) -> None:
    carpeta = Path(carpeta)
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        tmp = carpeta / (NOMBRE + ".tmp")
        tmp.write_text(json.dumps({"origen": origen, "catalogo": json.loads(datos)}, ensure_ascii=False),
                       encoding="utf-8")
        os.replace(tmp, carpeta / NOMBRE)
    except (OSError, ValueError):
        pass


def cargar_copia(carpeta: Path) -> Catalogo | None:
    try:
        d = json.loads((Path(carpeta) / NOMBRE).read_text(encoding="utf-8"))
        return leer(d["catalogo"], d.get("origen", ""))
    except (OSError, ValueError, KeyError, TypeError, CatalogoError):
        return None
