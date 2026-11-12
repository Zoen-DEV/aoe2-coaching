"""Arma el catálogo de contenido de AoE2C: los paquetes y catalogo.json.

Lee lo que ya está construido en build/ (raíz del monorepo) y escribe en build/catalogo/:

- guia-<id>-<versión>.zip: manifiesto del overlay + script .xs de cada guía
  (de content/guias/build.py).
- mod-<id>-<versión>.zip: la carpeta del mod tal como va en mods\\local
  (de content/mods/<id>/build.py), con su ficha content/mods/<id>/catalogo.json.
- Los mapas van como receta (content/mapas/mapas.json): la app los arma con el juego.
- catalogo.json: la lista, con la versión, el SHA-256 y la versión mínima de la app de
  cada elemento (formato en apps/desktop/catalogo.py).

Los .zip salen siempre iguales si no cambia su contenido (fechas fijas), así que su hash
solo cambia cuando cambia la guía o el mod. Esto es lo que publica el proceso
"contenido-*" de GitHub Actions (plan 7).

Uso: py content/catalogo.py [--salida CARPETA] [--sin-mods] [--mods-previos CARPETA]

--mods-previos  para cada mod sin armar en build/mods, usa CARPETA/mod-<id>-<versión>.zip
                (ya publicado). Lo usa GitHub Actions, donde no está el juego para armarlo
                (.github/scripts/mods_publicados.py baja esos .zip).

Al ejecutar la app desde el código, el panel usa build/catalogo/catalogo.json si existe.
"""

import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAIZ = HERE.parent
sys.path.insert(0, str(RAIZ / "apps" / "desktop"))
import catalogo as K  # noqa: E402

BUILD = RAIZ / "build"
GUIAS = BUILD / "guias"
XS = BUILD / "mods" / "guia-apertura-castillos" / "resources" / "_common" / "xs"
MAPAS = HERE / "mapas" / "mapas.json"
MODS = HERE / "mods"
MODS_ARMADOS = BUILD / "mods"
SALIDA = BUILD / "catalogo"
# Versión mínima de la app según el formato del manifiesto de la guía ("version" del manifiesto).
APP_MINIMA_GUIA = {2: "1.0.0", 3: "1.2.0"}  # 3: el .xsdat lleva la civilización y la tierlist
APP_MINIMA = "1.0.0"
FECHA_ZIP = (1980, 1, 1, 0, 0, 0)


def zip_fijo(destino: Path, archivos: list[tuple[str, Path]]) -> K.Paquete:
    """Zip con fechas y permisos fijos y en orden: mismo contenido, mismo hash."""
    with zipfile.ZipFile(destino, "w") as z:
        for nombre, ruta in sorted(archivos):
            info = zipfile.ZipInfo(nombre, FECHA_ZIP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, ruta.read_bytes(), compresslevel=9)
    return K.Paquete(destino.name, K.sha256_de(destino), destino.stat().st_size)


def guias(salida: Path) -> list[K.Elemento]:
    out = []
    manifiestos = sorted(GUIAS.glob("*.json"))
    if not manifiestos:
        raise SystemExit(f"no hay guías en {GUIAS}: ejecuta antes py content/guias/build.py")
    for ruta in manifiestos:
        m = json.loads(ruta.read_text(encoding="utf-8"))
        xs = XS / m["archivo_xs"]
        if not xs.is_file():
            raise SystemExit(f"falta {xs}: ejecuta antes py content/guias/build.py")
        if m.get("version") not in APP_MINIMA_GUIA:
            raise SystemExit(f"{ruta.name}: formato de manifiesto {m.get('version')} sin versión mínima de la app "
                             "(añádelo a APP_MINIMA_GUIA)")
        if "version_guia" not in m:
            raise SystemExit(f"{ruta.name}: le falta version_guia (vuelve a ejecutar build.py)")
        paquete = zip_fijo(salida / f"guia-{m['id']}-{m['version_guia']}.zip",
                           [(ruta.name, ruta), (xs.name, xs)])
        out.append(K.Elemento(
            "guia", m["id"], m["version_guia"], APP_MINIMA_GUIA[m["version"]],
            {"es": m["nombre"], "en": m["nombre"]}, {"es": m["descripcion"], "en": m["descripcion_en"]},
            {"archivo_xs": m["archivo_xs"], "nivel": m["nivel"], "mapas_recomendados": m["mapas_recomendados"]},
            paquete))
    return out


def mapas() -> list[K.Elemento]:
    out = []
    for m in json.loads(MAPAS.read_text(encoding="utf-8"))["mapas"]:
        datos = {"base": m["base"], "archivo": m["archivo"], "tipo": m["tipo"], "guias": m["guias"]}
        if m.get("imagen"):
            datos["imagen"] = m["imagen"]
        out.append(K.Elemento("mapa", m["id"], m["version"], m.get("app_minima", APP_MINIMA),
                              {"es": m["nombre"], "en": m["nombre"]}, m["descripcion"], datos))
    return out


def zip_previo(zip_: Path, destino: Path) -> K.Paquete:
    """Copia un paquete de mod ya publicado, sin cambiar sus bytes (ni su hash)."""
    try:
        with zipfile.ZipFile(zip_) as z:
            nombres = z.namelist()
            roto = z.testzip()
    except (OSError, zipfile.BadZipFile) as e:
        raise SystemExit(f"{zip_.name} no es un .zip válido: {e}")
    if roto or "info.json" not in nombres:
        raise SystemExit(f"{zip_.name}: {'archivo dañado: ' + roto if roto else 'le falta info.json en la raíz'}")
    shutil.copyfile(zip_, destino)
    return K.Paquete(destino.name, K.sha256_de(destino), destino.stat().st_size)


def mods(salida: Path, previos: Path | None = None) -> list[K.Elemento]:
    out = []
    for ficha in sorted(MODS.glob("*/catalogo.json")):
        f = json.loads(ficha.read_text(encoding="utf-8"))
        carpeta = ficha.parent.name
        armado = MODS_ARMADOS / carpeta
        if f.get("id") != carpeta:
            raise SystemExit(f"{ficha}: 'id' debe ser el nombre de la carpeta ({carpeta})")
        nombre = f"mod-{carpeta}-{f['version']}.zip"
        if (armado / "info.json").is_file():
            archivos = [(p.relative_to(armado).as_posix(), p) for p in armado.rglob("*") if p.is_file()]
            paquete = zip_fijo(salida / nombre, archivos)
        elif previos and (previos / nombre).is_file():
            paquete = zip_previo(previos / nombre, salida / nombre)
        elif previos:
            raise SystemExit(f"falta {nombre}: es una versión nueva del mod y no se puede armar sin el juego. "
                             f"Ármalo con py content/mods/{carpeta}/build.py, después py content/catalogo.py, "
                             f"y sube build/catalogo/{nombre} a la publicación mods-fuente")
        else:
            raise SystemExit(f"falta {armado}: ejecuta antes py content/mods/{carpeta}/build.py")
        out.append(K.Elemento("mod", carpeta, f["version"], f.get("app_minima", APP_MINIMA), f["nombre"],
                              f["descripcion"], {"carpeta": carpeta, "titulo": f["titulo"]}, paquete))
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    salida = Path(args[args.index("--salida") + 1]).resolve() if "--salida" in args else SALIDA
    previos = Path(args[args.index("--mods-previos") + 1]).resolve() if "--mods-previos" in args else None
    if salida.exists():
        shutil.rmtree(salida)
    salida.mkdir(parents=True)
    elementos = guias(salida) + mapas() + ([] if "--sin-mods" in args else mods(salida, previos))
    generado = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    texto = K.a_json(K.Catalogo(elementos), generado)
    try:
        cat = K.leer(texto, str(salida / K.NOMBRE), estricto=True)
    except K.CatalogoError as e:
        raise SystemExit(f"el catálogo no es válido: {e}")
    ids_mapas = {e.id for e in cat.de("mapa")}
    ids_guias = {e.id for e in cat.de("guia")}
    for e in cat.elementos:
        malos = set(e.datos.get("mapas_recomendados", [])) - ids_mapas | set(e.datos.get("guias", [])) - ids_guias
        if e.tipo in ("guia", "mapa") and malos:
            raise SystemExit(f"{e.tipo} {e.id}: recomienda ids que no están en el catálogo: {sorted(malos)}")
    (salida / K.NOMBRE).write_text(texto, encoding="utf-8")
    for e in cat.elementos:
        extra = f"  {e.paquete.archivo} ({e.paquete.tamano / 1024:.0f} KB)" if e.paquete else "  (se arma en la PC)"
        print(f"{e.tipo:5} {e.id:14} {e.version:8}{extra}")
    print(f"\n-> {salida / K.NOMBRE}")


if __name__ == "__main__":
    main()
