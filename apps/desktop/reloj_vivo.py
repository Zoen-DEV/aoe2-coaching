"""Reloj de una partida en curso, leído de su repetición mientras el juego la escribe.

El juego crea la repetición al empezar la partida y le va añadiendo operaciones
(analisis.py): las sincronizaciones hacen avanzar el reloj del juego. Este lector
sigue el archivo desde lo último que leyó (no lo relee entero) y da el tiempo de juego.

Juego limpio: de la partida en curso solo se saca el reloj y, del propio jugador, los
clics en las edades (para comparar con la guía). Los comandos de los demás jugadores
no se decodifican: se saltan sin mirar qué son.

Entre una escritura y la siguiente del juego, el reloj avanza solo con el reloj de pared
y la velocidad de la partida (1,7 en las clasificatorias), hasta EXTRAPOLAR segundos:
si el archivo deja de crecer más tiempo (pausa, o el juego escribe a trozos grandes), el
reloj se para en lo último extrapolado y nunca vuelve atrás. Cada vez que llegan datos
se apunta cuánto tardaron (retrasos), para ver en el log cómo escribe el juego.
"""

import logging
import struct
import time
from collections.abc import Callable
from pathlib import Path

import analisis as A

log = logging.getLogger("aoe2c")

EXTRAPOLAR = 8.0       # segundos de pared que el reloj sigue solo sin datos nuevos
VELOCIDAD = 1.7        # la de las clasificatorias, si la cabecera no dice otra
MAX_LECTURA = 8 << 20  # bytes que se leen como mucho de una vez
LOG_LLEGADAS = 12      # cuántas llegadas de datos se apuntan en el log por partida


class RelojVivo:
    def __init__(self, ruta: Path, jugador: int | None = None, velocidad: float = VELOCIDAD,
                 ahora: Callable[[], float] = time.monotonic):
        self.ruta = Path(ruta)
        self.jugador = jugador          # número del propio jugador (1 a 8): sus clics en las edades
        self.velocidad = velocidad if velocidad and velocidad > 0 else VELOCIDAD
        self.ahora = ahora
        self.ms = 0                     # tiempo de juego leído (milisegundos)
        self.edades: dict[int, float] = {}  # edad (2, 3, 4) -> segundo de juego del clic propio
        self.terminada = False          # llegó el fin de la partida o algo que no se entiende
        self.retrasos: list[float] = [] # segundos de pared entre llegadas de datos
        self._pos = 0                   # posición en el archivo de lo que hay en _buf
        self._buf = b""
        self._cuerpo = False            # ya se pasó la cabecera
        self._visto: float | None = None  # cuándo avanzó el reloj leído por última vez
        self._mostrado = 0.0            # lo último que dio tiempo(): nunca vuelve atrás

    # Lo llama el overlay cada segundo, más o menos.
    def actualizar(self) -> bool:
        """Lee lo nuevo del archivo. True si el reloj avanzó."""
        if self.terminada:
            return False
        try:
            with open(self.ruta, "rb") as f:
                f.seek(self._pos + len(self._buf))
                nuevo = f.read(MAX_LECTURA)
        except OSError:
            return False
        if not nuevo:
            return False
        self._buf += nuevo
        antes = self.ms
        self._procesar()
        if self.ms > antes:
            momento = self.ahora()
            if self._visto is not None and len(self.retrasos) < 1000:
                self.retrasos.append(round(momento - self._visto, 2))
                if len(self.retrasos) <= LOG_LLEGADAS:
                    log.info("reloj en vivo: %s s de juego, %.1f s desde la anterior llegada", self.ms // 1000,
                             self.retrasos[-1])
            self._visto = momento
            return True
        return False

    def _procesar(self) -> None:
        d = self._buf
        if not self._cuerpo:
            try:
                i = A._inicio_cuerpo(d)
            except A.AnalisisError:
                return  # cabecera o metadatos a medio escribir
            if i > len(d):
                return
            self._cuerpo = True
        else:
            i = 0
        while True:
            r = A.operacion(d, i)
            if r is None:
                break  # operación a medio escribir: se sigue desde ella la próxima vez
            tipo, i, valor = r
            if tipo == A.FIN:
                self.terminada = True
                break
            if tipo == A.OP_SYNC:
                self.ms += valor
            elif tipo == A.OP_ACCION and valor is not None:
                self._comando(*valor)
        self._pos += i
        self._buf = d[i:]

    def _comando(self, jugador: int, comando: int, datos: bytes) -> None:
        if self.jugador is None or jugador != self.jugador or comando != A.A_INVESTIGAR:
            return  # de otro jugador (o no interesa): ni se mira
        try:
            _, _, tech = struct.unpack_from("<Ihh", datos)
        except struct.error:
            return
        edad = A.EDADES.get(tech)
        if edad is not None and edad not in self.edades:
            self.edades[edad] = round(self.ms / 1000, 1)

    def tiempo(self) -> float:
        """Segundos de juego ahora: lo leído más lo que pasó desde entonces (como mucho
        EXTRAPOLAR segundos de pared a la velocidad de la partida). Nunca vuelve atrás."""
        t = self.ms / 1000
        if self._visto is not None and not self.terminada:
            t += min(max(0.0, self.ahora() - self._visto), EXTRAPOLAR) * self.velocidad
        self._mostrado = max(self._mostrado, t)
        return self._mostrado

    @property
    def leido(self) -> float:
        """Segundos de juego que trae el archivo (sin extrapolar)."""
        return self.ms / 1000

    def segundos_sin_datos(self) -> float | None:
        return None if self._visto is None else self.ahora() - self._visto


# --- Escritura poco a poco (pruebas y modo simulado) -------------------------------------


class EscritorPrueba:
    """Escribe una repetición de prueba a trozos, como el juego mientras se juega: la
    cabecera al principio y luego cada operación, sin el fin de la partida."""

    def __init__(self, ruta: Path, jugadores: list, **kw):
        import cabecera as CB
        CB.escribir_prueba(ruta, jugadores, **kw)
        datos = ruta.read_bytes()
        tam = struct.unpack_from("<I", datos)[0]
        meta = struct.pack("<II", 5, 500) + bytes(20) + struct.pack("<I", 0)
        ruta.write_bytes(datos[:tam] + meta + A.sync_prueba(0))
        self.ruta = ruta
        self.ms = 0

    def escribir(self, datos: bytes) -> None:
        with open(self.ruta, "ab") as f:
            f.write(datos)

    def avanzar(self, segundos: float, paso_ms: int = 500) -> None:
        """Sincronizaciones hasta sumar esos segundos de juego. Se escribe una operación
        más (de vista) detrás de la última, para que la sincronización corta se cierre."""
        objetivo = self.ms + int(segundos * 1000)
        trozos = b""
        while self.ms < objetivo:
            inc = min(paso_ms, objetivo - self.ms)
            trozos += A.sync_prueba(inc)
            self.ms += inc
        self.escribir(trozos + struct.pack("<I", A.OP_VISTA) + bytes(12))

    def terminar(self) -> None:
        self.escribir(struct.pack("<I", A.OP_POSTGAME))
