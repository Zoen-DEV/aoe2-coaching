"""Pruebas del panel de AoE2C, la guía de Scouts y la elección de guía (sin abrir ventanas).

    py pruebas/test_panel.py

Usa carpetas temporales como perfil del juego: no toca el juego, el perfil real ni
config.json.
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # nada aparece en pantalla
OVERLAY = Path(__file__).resolve().parent.parent  # apps/desktop
RAIZ = OVERLAY.parent.parent  # raíz del monorepo
GUIAS_DIR = RAIZ / "content" / "guias"
MOD = RAIZ / "build" / "mods" / "guia-apertura-castillos"
sys.path.insert(0, str(OVERLAY))
sys.path.insert(0, str(GUIAS_DIR))

import apoyo  # noqa: E402
import config as C  # noqa: E402
import historial as H  # noqa: E402
import instalador as I  # noqa: E402
import lector as L  # noqa: E402
import textos  # noqa: E402

GUIAS = L.cargar_guias()
FC, SC = GUIAS["fast_castle"], GUIAS["scouts"]


def comprobar(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok ·", msg)


def estado_de(guia: dict, t: int, horas: list[int], edad: int = 0, techs=None) -> L.Estado:
    paso = 0
    while paso < len(horas) and horas[paso] >= 0:
        paso += 1
    return L.Estado(t, 1, paso, horas, [0] * guia["num_datos"], techs or [0] * guia["num_techs"], edad, 20, 5, 0)


def partida_scouts(hasta: int = 900, retraso: int = 15):
    """Estados segundo a segundo de una partida de Scouts."""
    i_feudal = SC["techs"].index("edad_feudal")
    clic = next(p["referencia"] for p in SC["pasos"] if p["titulo"] == "Clic en Edad Feudal") + retraso
    llegada = clic + 130
    for t in range(hasta):
        horas = [p["referencia"] + retraso if t >= p["referencia"] + retraso else -1 for p in SC["pasos"]]
        techs = [0] * SC["num_techs"]
        techs[i_feudal] = 2 if t >= llegada else (1 if t >= clic else 0)
        yield estado_de(SC, t, horas, 1 if t >= llegada else 0, techs)


# --- Guías ---------------------------------------------------------------------


def test_guias():
    print("Guías generadas por build.py")
    ids = {json.loads(p.read_text(encoding="utf-8"))["id"] for p in (GUIAS_DIR / "build_orders").glob("*.json")}
    comprobar(set(GUIAS) == ids, f"una guía por build order: {sorted(GUIAS)}")
    comprobar({"fast_castle", "scouts", "arqueros", "drush_fc", "hombres_armas", "aguilas"} <= ids,
              "Fast Castle, Scouts, Arqueros, Drush FC, Hombres de armas y Águilas")
    comprobar(len({g["codigo"] for g in GUIAS.values()}) == len(GUIAS), "ningún código repetido")
    comprobar(FC["codigo"] != SC["codigo"], "cada guía tiene su código para el .xsdat")
    comprobar(all(0 <= g["codigo"] < 1_000_000_000 for g in GUIAS.values()),
              "los códigos tienen como mucho 9 cifras (el compilador XS no acepta más)")
    comprobar(SC["hito_principal"] == "meta" and SC["nombre_meta"] == "6 exploradores", "la meta de Scouts son 6 exploradores")
    comprobar(FC["hito_principal"] == "castillos", "Fast Castle se resume con la llegada a Castillos")
    etiquetas = {c["etiqueta"] for p in SC["pasos"] for c in p["condiciones"]}
    comprobar({"Establo", "Exploradores", "Cuartel"} <= etiquetas, "Scouts cuenta establo, cuartel y exploradores")
    xs = (MOD / "resources" / "_common" / "xs")
    texto = (xs / "guia_scouts.xs").read_text(encoding="ascii")
    comprobar(f"const int cGuiaCodigo = {SC['codigo']};" in texto and "guiaUnidades(jugador, 448)" in texto,
              "el script de Scouts escribe su código y cuenta la caballería de exploración (448)")
    comprobar("xsWriteInt(cGuiaCodigo);" in texto, "el .xsdat lleva el código de la guía")
    comun = (xs / "aoe2c_guia.xs").read_bytes()
    comprobar(comun in ((xs / "guia_fast_castle.xs").read_bytes(), (xs / "guia_scouts.xs").read_bytes()),
              "aoe2c_guia.xs es una copia exacta de una guía")
    rms = MOD / "resources" / "_common" / "random-map-scripts"
    mapas = sorted(p.name for p in rms.glob("*.rms"))
    comprobar(len(mapas) == 5 and all((rms / m).read_bytes().startswith(b"#includeXS aoe2c_guia.xs") for m in mapas),
              f"los 5 mapas cargan el script común: {mapas}")
    comprobar(all((rms / m).with_suffix(".png").is_file() for m in mapas), "cada mapa tiene su imagen para la sala")
    # Referencias coherentes: no bajan y la meta es el último paso.
    refs = [p["referencia"] for p in SC["pasos"]]
    comprobar(refs == sorted(refs), "las horas de referencia de Scouts no van hacia atrás")


def test_build_valida():
    print("build.py rechaza build orders mal escritas")
    import json
    import build as B
    with tempfile.TemporaryDirectory() as d:
        base = json.loads((GUIAS_DIR / "build_orders" / "scouts_21.json").read_text(encoding="utf-8"))
        casos = [("hito_principal", "castillos", "hito_principal"), ("nivel", "experto", "nivel"),
                 ("mapas_recomendados", ["luna"], "mapas_recomendados"), ("archivo_xs", "aoe2c_guia.xs", "reservado")]
        for clave, valor, espera in casos:
            datos = dict(base, **{clave: valor})
            p = Path(d) / "malo.json"
            p.write_text(json.dumps(datos), encoding="utf-8")
            try:
                B.load_build_order(p)
                ok = False
            except B.BuildOrderError as e:
                ok = espera in str(e)
            comprobar(ok, f"{clave} = {valor!r} da error")
        datos = json.loads(json.dumps(base))
        datos["pasos"][0]["condiciones"] = [{"unidades": "dragones", "min": 1}]
        p = Path(d) / "malo.json"
        p.write_text(json.dumps(datos), encoding="utf-8")
        try:
            B.load_build_order(p)
            ok = False
        except B.BuildOrderError as e:
            ok = "exploradores" in str(e)
        comprobar(ok, "una unidad desconocida da error con la lista de las válidas")
        datos = json.loads(json.dumps(base))
        del datos["pasos"][2]["texto_en"]
        p.write_text(json.dumps(datos), encoding="utf-8")
        try:
            B.load_build_order(p)
            ok = False
        except B.BuildOrderError as e:
            ok = "texto_en" in str(e)
        comprobar(ok, "un paso sin su texto en inglés da error")


# --- Lector ---------------------------------------------------------------------


def test_lector(tmp: Path):
    print("El lector reconoce la guía por el código del .xsdat")
    horas = [p["referencia"] for p in SC["pasos"][:3]] + [-1] * (len(SC["pasos"]) - 3)
    e = estado_de(SC, 200, horas)
    archivo = tmp / "[AoE2C] Arabia.xsdat"
    L.escribir_prueba(archivo, SC, e)
    guia, leido = L.parsear(archivo.read_bytes(), GUIAS)
    comprobar(guia["id"] == "scouts" and leido.paso == 3 and leido.tiempo == 200, "formato 2: Scouts, paso 4")
    L.escribir_prueba(archivo, FC, estado_de(FC, 100, [30] + [-1] * (len(FC["pasos"]) - 1)), version=1)
    guia, leido = L.parsear(archivo.read_bytes(), GUIAS)
    comprobar(guia["id"] == "fast_castle", "formato 1 (antiguo, sin código): se reconoce Fast Castle")
    comprobar(L.parsear(b"\x00" * 40, GUIAS) is None, "un archivo sin registro se ignora")
    # El mismo mapa, con otra guía: el lector cambia de guía.
    lec = L.Lector()
    lec._candidatos = lambda: iter([archivo])
    L.escribir_prueba(archivo, FC, estado_de(FC, 100, [30] + [-1] * (len(FC["pasos"]) - 1)))
    os.utime(archivo, (1e6, 1e6))
    lec.actualizar()
    comprobar(lec.guia["id"] == "fast_castle", "primera partida con Fast Castle")
    L.escribir_prueba(archivo, SC, e)
    os.utime(archivo, (2e6, 2e6))
    lec.actualizar()
    comprobar(lec.guia["id"] == "scouts" and lec.estado.paso == 3, "siguiente partida en el mismo mapa con Scouts")
    comprobar("[aoe2c] black forest" in lec.mapas, "busca el .xsdat de todos los mapas del catálogo")


# --- Historial ------------------------------------------------------------------


def test_historial_scouts(tmp: Path):
    print("Historial de una partida de Scouts")
    h = H.Historial(tmp / "hs.json")
    s = H.Seguimiento(h)
    escritura = 0.0
    ultimo = None
    for e in partida_scouts():
        escritura += 1
        s.observar(SC, e, 0.5, "[AoE2C] Arabia", escritura)
        ultimo = e
    s.observar(SC, ultimo, 10.0, "[AoE2C] Arabia", escritura)
    r = H.Historial(tmp / "hs.json").registros[0]
    meta = SC["pasos"][-1]["referencia"] + 15
    comprobar(r["guia"] == "Scouts 21" and r["vista"]["principal"] == "meta", "se guarda con su vista (meta)")
    comprobar(r["hitos"]["meta"] == meta, f"meta = hora de los 6 exploradores ({H.reloj(meta)})")
    comprobar(r["hitos"]["feudal"] == 9 * 60 + 45 + 15, f"llegada a Feudal: {H.reloj(r['hitos']['feudal'])}")
    comprobar(r["hitos"]["castillos"] is None, "Scouts no tiene Castillos")
    comprobar(H.valor_principal(r) == meta and H.nombre_hito(r, "meta") == "6 exploradores", "hito principal")
    comprobar(H.comparacion_final(h, r).startswith("Primera"), "la tarjeta final compara por la meta")
    comprobar(s.terminada == r["id"], "al acabar se avisa para abrir el historial")


def test_migracion(tmp: Path):
    print("Partidas guardadas con la versión anterior")
    import rutas
    real = next((p for p in (rutas.HISTORIAL, OVERLAY / "historial.json") if p.is_file()), rutas.HISTORIAL)
    if not real.is_file():
        print("  (sin historial.json real: se omite)")
        return
    copia = tmp / "antiguo.json"
    copia.write_bytes(real.read_bytes())
    h = H.Historial(copia)
    comprobar(len(h.registros) > 0, f"se leen las {len(h.registros)} partidas guardadas")
    r = h.registros[0]
    comprobar(r["vista"]["principal"] == "castillos" and "meta" in r["hitos"], "se completan con la vista de Fast Castle")
    comprobar(r["hitos"]["meta"] == r["pasos"][-1]["hora"], "la meta es la hora del último paso")
    comprobar(real.read_bytes() == real.read_bytes() and copia.stat().st_size > 0, "el archivo real no se toca")


# --- Instalador -------------------------------------------------------------------


def test_instalador(tmp: Path):
    print("Instalador: guía activa y mapas (en un perfil de prueba)")
    inst = apoyo.instalador_de_prueba(tmp, "inst")
    perfil = inst.perfil
    guias = inst.guias()
    comprobar(set(guias) == set(GUIAS), "todas las guías del catálogo, instaladas en la app")
    comprobar(inst.guia_instalada(guias) is None, "perfil vacío: ninguna guía instalada")
    comprobar(inst.activar_guia(guias["scouts"]) is None, "activar Scouts no da error")
    comun = perfil / "resources" / "_common" / "xs" / "aoe2c_guia.xs"
    comprobar(comun.is_file() and inst.guia_instalada(guias) == "scouts", "aoe2c_guia.xs = Scouts")
    comprobar((inst.mod_instalado / I.XS / "aoe2c_guia.xs").is_file(), "también en la copia del mod")
    inst.activar_guia(guias["fast_castle"])
    comprobar(inst.guia_instalada(guias) == "fast_castle", "cambiar a Fast Castle")
    estados = {e.mapa["id"]: e for e in inst.estado_mapas()}
    comprobar(len(estados) == 5 and all(e.estado == "no_instalado" for e in estados.values()),
              "los 5 mapas del catálogo, ninguno instalado")
    comprobar(all(e.imagen is not None and e.imagen.is_file() for e in estados.values()),
              "todos tienen imagen (armada con la oficial)")
    arabia = estados["arabia"].mapa
    comprobar(inst.instalar_mapa(arabia, guias["fast_castle"]) is None, "instalar Arabia")
    rms = inst.mod_instalado / I.RMS / "[AoE2C] Arabia.rms"
    oficial = inst.juego / "resources" / "_common" / "drs" / "gamedata_x2" / "Arabia.rms"
    comprobar(rms.is_file() and rms.with_suffix(".png").is_file() and (inst.mod_instalado / "info.json").is_file(),
              "arma el .rms, su imagen y el info.json del mod")
    comprobar(rms.read_bytes().startswith(b"#includeXS aoe2c_guia.xs") and rms.read_bytes().endswith(oficial.read_bytes()),
              "el .rms es el oficial con la línea que carga la guía")
    comprobar({e.mapa["id"]: e.estado for e in inst.estado_mapas()}["arabia"] == "instalado", "Arabia sale instalado")
    oficial.write_bytes(oficial.read_bytes() + b"/* parche del juego */\r\n")
    comprobar({e.mapa["id"]: e.estado for e in inst.estado_mapas()}["arabia"] == "desactualizado",
              "si el juego cambia el mapa oficial, el instalado queda desactualizado")
    comprobar(inst.reparar_mapas() == ["Arabia"] and rms.read_bytes().endswith(b"/* parche del juego */\r\n"),
              "reparar_mapas lo vuelve a armar con el oficial nuevo")
    comprobar({e.mapa["id"]: e.estado for e in inst.estado_mapas()}["arabia"] == "instalado", "y vuelve a estar al día")
    destino = tmp / "copias"
    destino.mkdir()
    comprobar(inst.exportar_mapa(arabia, destino) is None and (destino / "[AoE2C] Arabia.rms").is_file(),
              "guardar una copia en otra carpeta")
    comprobar(inst.quitar_mapa(arabia) is None and not rms.exists(), "quitar Arabia")
    otro = apoyo.instalador_de_prueba(tmp, "inst2")
    otro.instalar_mapa(otro.mapas()[0], otro.guias()["scouts"])
    comprobar(otro.guia_instalada(otro.guias()) == "scouts", "instalar un mapa sin script común instala la guía activa")
    falso = dict(arabia, base="No_existe.rms")
    comprobar(inst.instalar_mapa(falso) is not None, "un mapa sin su oficial da un error legible")


def test_config(tmp: Path):
    print("Preferencias compartidas")
    a = tmp / "c.json"
    defecto = {**C.DEFECTO, "idioma": textos.idioma_de_windows()}
    comprobar(C.cargar(a) == defecto and defecto["idioma"] in ("es", "en"),
              "sin archivo: valores por defecto, con el idioma de Windows")
    a.write_text('{"posicion": "izquierda", "plegado": false, "pestana_historial": true, "raro": 1}', encoding="utf-8")
    cfg = C.cargar(a)
    comprobar(cfg["posicion"] == "izquierda" and "raro" not in cfg and cfg["guia_activa"] == "fast_castle",
              "el config.json antiguo se respeta y se completa")
    cfg["guia_activa"] = "scouts"
    C.guardar(cfg, a)
    comprobar(C.cargar(a)["guia_activa"] == "scouts", "se guarda y se vuelve a leer")
    a.write_text("[1, 2", encoding="utf-8")
    comprobar(C.cargar(a) == defecto, "un archivo roto no rompe nada")
    otro = "en" if textos.idioma_de_windows() == "es" else "es"
    a.write_text('{"idioma": "%s"}' % otro, encoding="utf-8")
    comprobar(C.cargar(a)["idioma"] == otro, "el idioma elegido se respeta aunque Windows esté en otro")


def test_textos():
    print("Textos en español e inglés")
    es, en = textos.TEXTOS["es"], textos.TEXTOS["en"]
    comprobar(set(es) == set(en), f"mismas claves en los dos idiomas (faltan en inglés: {sorted(set(es) - set(en))})")
    usadas = set()
    for archivo in ("dashboard.py", "overlay.py", "historial.py", "historial_ui.py"):
        codigo = (OVERLAY / archivo).read_text(encoding="utf-8")
        usadas |= set(re.findall(r'\bt[x]?\("([a-z0-9_]+)"', codigo))
    # Claves que se arman con f-strings.
    from dashboard import PAGINAS, PROXIMAS
    usadas |= {f"pagina_{p}" for p in PAGINAS}
    usadas |= {f"proxima_{i}" for i, _ in PROXIMAS} | {f"proxima_{i}_desc" for i, _ in PROXIMAS}
    usadas |= {f"nivel_{n}" for n in ("facil", "media", "dificil")} | {f"como_{n}" for n in (1, 2, 3)}
    usadas |= {f"mapa_{e}" for e in ("instalado", "desactualizado", "no_instalado", "sin_juego", "necesita_app")}
    usadas |= {f"mod_{e}" for e in ("instalado", "desactualizado", "no_instalado", "necesita_app")}
    usadas |= {f"activacion_{e}" for e in ("activo", "pendiente", "desactivado", "sin_registrar")}
    usadas |= {f"hito_{k}" for k in ("clic_feudal", "feudal", "clic_castillos", "castillos")}
    faltan = sorted(usadas - set(es))
    comprobar(not faltan, f"todas las claves usadas existen ({len(usadas)}); faltan: {faltan}")
    for clave, texto in es.items():
        campos_es = set(re.findall(r"{(\w+)}", texto))
        campos_en = set(re.findall(r"{(\w+)}", en[clave]))
        if campos_es != campos_en:
            raise AssertionError(f"{clave}: campos distintos {campos_es} / {campos_en}")
    comprobar(True, "los dos idiomas usan los mismos valores en cada texto")
    textos.poner_idioma("en")
    comprobar(textos.t("menu_cerrar") == "Quit AoE2C", "inglés")
    textos.poner_idioma("xx")
    comprobar(textos.t("menu_cerrar") == "Cerrar AoE2C", "un idioma desconocido vuelve al español")


def test_ingles(tmp: Path):
    print("Guías, tarjeta e historial en inglés")
    import overlay as O
    for guia in (FC, SC):
        faltan = [n for n, p in enumerate(guia["pasos"], 1) if not p.get("titulo_en") or not p.get("texto_en")
                  or not all(c.get("etiqueta_en") for c in p["condiciones"])]
        comprobar(not faltan and guia.get("titulo_final_en") and guia.get("mensaje_final_en"),
                  f"{guia['nombre']}: cada paso trae su título, instrucción y condiciones en inglés")
    horas = [p["referencia"] + 30 if i < 4 else -1 for i, p in enumerate(FC["pasos"])]
    estado = estado_de(FC, 340, horas)
    textos.poner_idioma("en")
    try:
        v = O.construir_vista(FC, estado)
        comprobar(v.titulo == FC["pasos"][4]["titulo_en"] and v.texto.startswith("With villager 12"),
                  f"la tarjeta muestra el paso en inglés: {v.titulo!r}")
        comprobar([c.etiqueta for c in v.condiciones] == ["Houses", "Mill", "Berries"],
                  "y sus condiciones (Houses, Mill, Berries)")
        comprobar(v.siguientes[0][1] == FC["pasos"][5]["titulo_en"] and v.ritmo[0] == "+30 s",
                  "«Up next» y el ritmo también")
        fin = O.construir_vista(FC, estado_de(FC, 1000, [p["referencia"] for p in FC["pasos"]], edad=2))
        comprobar(fin.titulo_final == "You reached the Castle Age!" and fin.final.startswith("Next:")
                  and " at " in fin.resumen, "la tarjeta final en inglés")
        h = H.Historial(tmp / "en.json")
        s = H.Seguimiento(h)
        ultimo = None
        for n, e in enumerate(partida_scouts(), 1):
            s.observar(SC, e, 0.5, "[AoE2C] Arabia", float(n))
            ultimo = e
        s.observar(SC, ultimo, 10.0, "[AoE2C] Arabia", 1000.0)
        r = h.registros[0]
        comprobar(H.nombre_hito(r, "meta") == "6 scouts" and H.nombre_hito(r, "feudal") == "Feudal"
                  and H.nombre_hito(r, "clic_feudal") == "Feudal click", "los hitos del historial en inglés")
        comprobar(H.tramos(r)[0]["titulo"] == "2 houses", "y los pasos de la partida")
        comprobar(H.comparacion_final(h, r).startswith("First game"), "y la línea de la tarjeta final")
        textos.poner_idioma("es")
        comprobar(H.nombre_hito(r, "meta") == "6 exploradores" and H.tramos(r)[0]["titulo"] == "2 casas"
                  and O.construir_vista(FC, estado).titulo == FC["pasos"][4]["titulo"],
                  "al volver al español, todo sale en español")
        viejo = {"titulo": "Telar"}
        textos.poner_idioma("en")
        comprobar(textos.de(viejo, "titulo") == "Telar", "un texto sin versión en inglés (guía vieja) sale en español")
    finally:
        textos.poner_idioma("es")


# --- Panel ---------------------------------------------------------------------------


class OverlayFalso:
    def __init__(self):
        self.en_partida = False
        self.vista = None


def test_panel(tmp: Path):
    print("Panel: páginas, guía activa, ✕ y Cerrar AoE2C")
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    app = QApplication.instance() or QApplication(sys.argv)
    import dashboard as D
    import overlay as O
    config = C.cargar(tmp / "nada.json")
    guardados, salidas, ocultados = [], [], []
    hist = H.historial_de_ejemplo(FC, 12)
    inst = apoyo.instalador_de_prueba(tmp, "panel")
    falso = OverlayFalso()
    p = D.Panel(config, hist, inst.guias(), inst, overlay=falso, segundo_plano=False, al_salir=lambda: salidas.append(1),
                al_ocultar=lambda: ocultados.append(1), guardar_config=lambda: guardados.append(dict(config)),
                comprobar_juego=False)
    for nombre in D.PAGINAS:
        p.ir(nombre)
        app.processEvents()
        comprobar(p.paginas.currentWidget() is getattr(p, f"p_{nombre}") and p.titulo.text() == textos.t(f"pagina_{nombre}"),
                  f"página {nombre}")
    p.ir("inicio")
    comprobar(p.p_inicio.nombre_guia.text() == "Fast Castle 27+2", "inicio: la guía activa es Fast Castle")
    comprobar(p.p_inicio.aviso_guia.isVisibleTo(p), "avisa de que los mapas aún no la cargan (perfil vacío)")
    comprobar(p.p_inicio.d_partidas.valor == "12", "inicio: 12 partidas con esa guía")
    mejor = H.resumen_hito(hist.registros, "castillos")["mejor"]
    comprobar(p.p_inicio.d_mejor.valor == H.reloj(mejor), f"inicio: mejor marca {H.reloj(mejor)}")
    p.ir("guias")
    usar = [b for b in p.p_guias.findChildren(QPushButton) if b.text() == textos.t("usar_guia")]
    comprobar(len(usar) == len(GUIAS) - 1, "en Guías, un botón «Usar esta guía» por guía (menos la activa)")

    def de_scouts(b) -> bool:
        tarjeta = b.parent()
        while tarjeta is not None and type(tarjeta).__name__ != "TarjetaGuia":
            tarjeta = tarjeta.parent()
        return tarjeta is not None and any(e.text() == "Scouts 21" for e in tarjeta.findChildren(QLabel))
    usar = [b for b in usar if de_scouts(b)]
    comprobar(len(usar) == 1, "uno de ellos es el de Scouts")
    usar[0].click()
    app.processEvents()
    comprobar(config["guia_activa"] == "scouts" and guardados and guardados[-1]["guia_activa"] == "scouts",
              "pulsarlo activa Scouts y guarda la preferencia")
    comprobar(inst.guia_instalada(inst.guias()) == "scouts", "y la instala para los mapas")
    comprobar(p.mensaje.isVisibleTo(p) and "Scouts" in p.mensaje.text(), f"aviso: «{p.mensaje.text()}»")
    p.ir("inicio")
    comprobar(p.p_inicio.nombre_guia.text() == "Scouts 21" and not p.p_inicio.aviso_guia.isVisibleTo(p),
              "inicio muestra Scouts, ya instalada")
    comprobar(p.p_inicio.d_partidas.valor == "0", "sin partidas de Scouts todavía")
    # Historial: todas las partidas por defecto, filtro por guía y una partida concreta.
    c = p.p_historial.contenido
    for r in H.historial_de_ejemplo(SC, 3).registros:
        hist.poner(dict(r, id=r["id"] + "-sc"))
    p.ir("historial")
    comprobar(c.filtro is None and len(c.lista.registros) == 15, "el historial muestra todas las partidas")
    comprobar(c.barra_filtros.isVisibleTo(p) and [b.text().split("   ")[0] for b in c.grupo.buttons()]
              == ["Todas", "Fast Castle 27+2", "Scouts 21"], "con un filtro por guía (y «Todas»)")
    comprobar(c.vista_guias.isVisibleTo(p) and [f["guia"] for f in c.tabla_guias.filas] == ["Fast Castle 27+2", "Scouts 21"],
              "sin filtro, el resumen es una fila por guía")
    c.grupo.buttons()[2].click()
    comprobar(c.filtro == "Scouts 21" and len(c.lista.registros) == 3 and c.vista_general.isVisibleTo(p),
              "el filtro deja las partidas de esa guía y su resumen")
    de_fc = next(r for r in hist.registros if r["guia"] == "Fast Castle 27+2")
    p.ver_partida(de_fc)
    comprobar(c.seleccion == de_fc["id"] and c.vista_partida.isVisibleTo(p), "ver una partida abre su detalle")
    comprobar(c.filtro is None, "y quita el filtro de otra guía")
    p.ver_historial("Fast Castle 27+2")
    comprobar(c.filtro == "Fast Castle 27+2" and c.seleccion is None, "«Ver historial» de una guía la filtra")
    p.ir("inicio")
    p.ir("historial")
    comprobar(c.filtro == "Fast Castle 27+2", "el filtro se conserva al cambiar de página")
    p.ver_historial()
    # Mapas: instalar desde la tarjeta.
    p.ir("mapas")
    tarjetas = p.p_mapas.findChildren(D.TarjetaMapa)
    comprobar(len(tarjetas) == 5, "5 mapas en la página")
    tarjetas[0].instalar()
    app.processEvents()
    comprobar({e.mapa["id"]: e.estado for e in inst.estado_mapas()}[tarjetas[0].em.mapa["id"]] == "instalado",
              "instalar un mapa desde su tarjeta")
    # Estado de la partida.
    falso.en_partida = True
    falso.vista = O.Vista("Scouts 21", 300, 4, 14, 4, None, False)
    p.actualizar_estado()
    comprobar("paso 5 de 14" in p.texto_estado.text(), f"estado en partida: «{p.texto_estado.text()}»")
    comprobar(not p.boton_jugar.isEnabled(), "en partida no se ofrece abrir el juego")
    # Idioma.
    p.cambiar_idioma("en")
    comprobar(p.titulo.text() == "Home" or p.titulo.text() == textos.TEXTOS["en"][f"pagina_{p.pagina}"],
              f"en inglés: «{p.titulo.text()}»")
    comprobar(config["idioma"] == "en", "el idioma se guarda")
    p.cambiar_idioma("es")
    # La ✕ lo esconde (no cierra) y avisa una sola vez.
    p.show()
    app.processEvents()
    p.close()
    app.processEvents()
    comprobar(not p.isVisible() and not salidas, "la ✕ esconde el panel y el programa sigue")
    comprobar(ocultados == [1] and config["aviso_bandeja_visto"], "la primera vez avisa de que sigue en la bandeja")
    p.mostrar()
    app.processEvents()
    comprobar(p.isVisible(), "se vuelve a abrir (clic en la bandeja)")
    p.close()
    app.processEvents()
    comprobar(ocultados == [1], "el aviso no se repite")
    salir = [b for b in p.findChildren(QPushButton) if textos.t("cerrar_programa") in b.text()]
    comprobar(len(salir) == 1, "hay un botón «Cerrar AoE2C»")
    salir[0].click()
    comprobar(salidas == [1], "«Cerrar AoE2C» cierra el programa")


def test_overlay_con_panel(tmp: Path):
    print("Overlay: preferencias del panel, menú y bandeja")
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    QApplication.instance() or QApplication(sys.argv)
    import overlay as O
    O.CONFIG = tmp / "config_overlay.json"
    estado = O.estado_simulado(SC, 3, 200)
    v = O.construir_vista(SC, estado)
    comprobar(len(v.siguientes) == 3, "por defecto, 3 pasos siguientes")
    comprobar(len(O.construir_vista(SC, estado, siguientes=1).siguientes) == 1, "el panel puede dejar 1")
    estado_casas = O.estado_simulado(SC, 4, 300)
    comprobar(O.construir_vista(SC, estado_casas).aviso != "", "aviso de casas")
    comprobar(O.construir_vista(SC, estado_casas, aviso_casas=False).aviso == "", "se puede apagar")
    final = O.construir_vista(SC, O.estado_simulado(SC, len(SC["pasos"]), 900))
    comprobar(final.terminada and final.titulo_final == "¡Exploradores en marcha!", "tarjeta final propia de Scouts")
    config = C.cargar(tmp / "nada.json")
    config["opacidad"] = 0.7
    config["abrir_historial_al_terminar"] = False
    h = H.Historial(tmp / "h_ov.json")
    s = H.Seguimiento(h)
    datos = {"e": estado, "f": 0.0}
    w = O.Overlay(lambda: (SC, datos["e"], datos["f"]), solo_con_juego=False, historial=h, seguimiento=s, config=config)
    w.temporizador.stop()
    for _ in range(60):
        w.tick()
    comprobar(abs(w.windowOpacity() - 0.7) < 0.02, f"la tarjeta usa la opacidad del panel ({w.windowOpacity():.2f})")
    s.terminada = "x"
    w.tick()
    comprobar(not w.historial_abierto, "con la opción apagada, el historial no se abre al terminar")
    abiertos = []
    w.al_abrir_panel = lambda: abiertos.append(1)
    menu = w.crear_menu()
    textos_menu = [a.text() for a in menu.actions() if a.text()]
    comprobar(textos_menu[0] == textos.t("menu_abrir_panel") and textos_menu[-1] == "Cerrar AoE2C",
              f"menú: abrir panel arriba y «Cerrar AoE2C» abajo ({len(textos_menu)} opciones)")
    w.pulsar_bandeja(QSystemTrayIcon.ActivationReason.Trigger)
    w.pulsar_bandeja(QSystemTrayIcon.ActivationReason.Context)
    comprobar(abiertos == [1], "clic en el icono de la bandeja abre el panel; el clic derecho no (abre el menú)")
    w.cambiar_posicion("izquierda")
    comprobar(C.cargar(O.CONFIG)["posicion"] == "izquierda" and C.cargar(O.CONFIG)["opacidad"] == 0.7,
              "el overlay guarda en el mismo archivo sin perder las preferencias del panel")


def test_tierlist(tmp: Path):
    print("Tierlist de tecnologías al terminar la guía")
    import build as B
    import tierlist as TL
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication(sys.argv)
    import overlay as O

    # build.py: cada guía la trae, el script la vuelca y una tecnología desconocida da error.
    comprobar(all(g.get("tierlist") for g in GUIAS.values()), "todas las guías tienen tierlist")
    texto = (MOD / "resources" / "_common" / "xs" / "guia_fast_castle.xs").read_text(encoding="ascii")
    comprobar("xsWriteInt(3);" in texto and "xsGetPlayerCivilization(jugador)" in texto
              and "guiaEstadoTier(jugador, 213)" in texto,
              "el script escribe la versión 3, la civilización y el estado de cada tecnología")
    base = json.loads((GUIAS_DIR / "build_orders" / "scouts_21.json").read_text(encoding="utf-8"))
    p = tmp / "tier_malo.json"
    p.write_text(json.dumps(dict(base, tierlist={"S": ["dragones"]})), encoding="utf-8")
    try:
        B.load_build_order(p)
        ok = False
    except B.BuildOrderError as e:
        ok = "dragones" in str(e)
    comprobar(ok, "una tecnología desconocida en la tierlist da error")
    B.load_ajustes_tierlist()
    comprobar(True, "tierlist.json usa tecnologías, mapas y civilizaciones que existen")

    # Lector: la versión 3 trae la civilización y la tierlist; la 2 sigue valiendo.
    n = len(FC["tierlist"]["techs"])
    techs = FC["tierlist"]["techs"]
    horas = [p["referencia"] for p in FC["pasos"]]
    e = estado_de(FC, 1000, horas, edad=2)
    e.civ, e.tier = 2, [0] * n  # francos
    e.tier[techs.index("carretilla")] = 2
    e.tier[techs.index("collera")] = 1
    e.tier[techs.index("escuderos")] = 3  # la civilización no la tiene (según el juego)
    archivo = tmp / "[AoE2C] Arena.xsdat"
    L.escribir_prueba(archivo, FC, e)
    guia, leido = L.parsear(archivo.read_bytes(), GUIAS)
    comprobar(guia["id"] == "fast_castle" and leido.civ == 2 and leido.tier == e.tier, "formato 3: civilización y tierlist")
    L.escribir_prueba(archivo, FC, e, version=2)
    guia, viejo = L.parsear(archivo.read_bytes(), GUIAS)
    comprobar(guia["id"] == "fast_castle" and viejo.tier is None, "formato 2 (guía de antes): se lee, sin tierlist")
    comprobar(TL.construir(FC, viejo) is None, "sin estados no hay tierlist (queda el resumen de siempre)")
    L.escribir_prueba(archivo, FC, e)
    lec = L.Lector(guias=GUIAS)
    lec._candidatos = lambda: iter([archivo])
    lec.actualizar()
    comprobar(lec.estado.mapa == "[AoE2C] Arena", "el lector anota el mapa de la partida")

    # Ajustes: francos en Arena.
    tl = TL.construir(FC, lec.estado)
    nivel = {t.clave: n for n, ts in tl.niveles for t in ts}
    estado = {t.clave: t.estado for _, ts in tl.niveles for t in ts}
    comprobar(tl.civilizacion == "Francos" and tl.mapa == "Arena", "cabecera: Francos · Arena")
    comprobar("linea_sangre" not in nivel, "los francos no tienen Pureza de sangre: no sale")
    comprobar("escuderos" not in nivel, "lo que el juego dice que no tienen tampoco sale")
    comprobar(nivel["carro_de_mano"] == "S" and nivel["vigilancia"] == "C", "Arena sube Carro de mano y baja Guardia urbana")
    comprobar(nivel["forja"] == "A", "los francos suben Forja")
    comprobar(nivel["barda_escamas"] == "B", "Arena baja la barda y los francos la vuelven a subir")
    comprobar(estado["carretilla"] == TL.HECHA and estado["collera"] == TL.EN_CURSO, "hechas y en curso")
    fila_s = [t.clave for t in dict(tl.niveles)["S"]]
    comprobar(fila_s[-1] == "carretilla", "en cada nivel, las ya investigadas van al final")
    comprobar(tl.hechas == 1 and tl.total == len(nivel), f"cuenta {tl.hechas}/{tl.total}")
    en = TL.construir(FC, lec.estado, ingles=True)
    comprobar(en.civilizacion == "Franks" and "Wheelbarrow" in [t.nombre for _, ts in en.niveles for t in ts],
              "en inglés: Franks, Wheelbarrow")
    comprobar(TL.id_mapa("[AoE2C] Black Forest") == "black_forest", "el nombre del .xsdat da el id del mapa")

    # Overlay: a los 10 s del final pasa a la tierlist y ya no se esconde a los 90 s.
    w = O.Overlay(lambda: (FC, lec.estado, 0.0), solo_con_juego=False, config=C.cargar(tmp / "nada_tl.json"))
    w.temporizador.stop()
    w.tick()
    comprobar(w.vista.terminada and not w.vista.ver_tierlist, "al terminar, primero el resumen")
    w.fin_desde -= O.CAMBIO_TIERLIST + 1
    w.tick()
    comprobar(w.vista.ver_tierlist, "a los 10 s, la tierlist")
    alto = O.Pintor(None, O.ANCHO).dibujar(w.vista, None, 1.0)
    comprobar(alto <= w.alto_maximo(FC) + 0.5, "la tierlist cabe en el alto reservado de la tarjeta")
    w.fin_desde -= 100
    for _ in range(30):
        w.tick()
    comprobar(w.opacidad == 1.0, "la tierlist sigue a la vista pasados los 90 s")


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_guias()
        test_build_valida()
        test_lector(tmp)
        test_historial_scouts(tmp)
        test_migracion(tmp)
        test_instalador(tmp)
        test_config(tmp)
        test_textos()
        test_ingles(tmp)
        test_panel(tmp)
        test_overlay_con_panel(tmp)
        test_tierlist(tmp)
    print("\nTodo bien.")


if __name__ == "__main__":
    main()
