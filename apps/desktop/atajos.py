"""Atajo de teclado global (funciona con el juego delante), para mostrar u ocultar el
panel Match Info.

Usa RegisterHotKey de Windows: el sistema avisa a AoE2C cuando se pulsa la combinación
(y esa pulsación no llega al juego). No lee ni envía nada al juego. Si otra aplicación
ya usa la combinación, no se registra y queda anotado en el log. Fuera de Windows no hace nada.
"""

import ctypes
import logging
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication

log = logging.getLogger("aoe2c")

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
MODIFICADORES = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT,
                 "mayús": MOD_SHIFT, "win": MOD_WIN}
TECLAS = {**{f"f{n}": 0x6F + n for n in range(1, 13)}, "inicio": 0x24, "home": 0x24, "fin": 0x23, "end": 0x23,
          "insert": 0x2D, "supr": 0x2E, "delete": 0x2E, "pausa": 0x13, "pause": 0x13}


def parsear(texto: str) -> tuple[int, int] | None:
    """"Ctrl+Alt+M" -> (modificadores, código de tecla virtual); None si no se entiende.
    Hace falta al menos un modificador (salvo las teclas F) para no quitarle teclas al juego."""
    partes = [p.strip().lower() for p in str(texto or "").split("+") if p.strip()]
    if not partes:
        return None
    *mods, tecla = partes
    if any(m not in MODIFICADORES for m in mods):
        return None
    valor = 0
    for m in mods:
        valor |= MODIFICADORES[m]
    if len(tecla) == 1 and (tecla.isascii() and tecla.isalnum()):
        vk = ord(tecla.upper())
    elif tecla in TECLAS:
        vk = TECLAS[tecla]
    else:
        return None
    if not valor and not tecla.startswith("f"):
        return None
    return valor, vk


class AtajoGlobal(QAbstractNativeEventFilter):
    _siguiente_id = 0xA0E2

    def __init__(self, al_pulsar):
        super().__init__()
        self.al_pulsar = al_pulsar
        self.id = AtajoGlobal._siguiente_id
        AtajoGlobal._siguiente_id += 1
        self.texto = ""
        self.activo = False
        self._instalado = False

    def poner(self, texto: str) -> bool:
        """Registra la combinación (quita la anterior). True si quedó activa."""
        self.quitar()
        self.texto = texto
        combinacion = parsear(texto)
        if combinacion is None or sys.platform != "win32":
            if combinacion is None and texto:
                log.warning("atajo no válido: %r", texto)
            return False
        if not self._instalado:
            QApplication.instance().installNativeEventFilter(self)
            self._instalado = True
        mods, vk = combinacion
        self.activo = bool(ctypes.windll.user32.RegisterHotKey(None, self.id, mods | MOD_NOREPEAT, vk))
        if not self.activo:
            log.warning("no se pudo registrar el atajo %s (¿lo usa otra aplicación?)", texto)
        return self.activo

    def quitar(self):
        if self.activo:
            ctypes.windll.user32.UnregisterHotKey(None, self.id)
            self.activo = False

    def nativeEventFilter(self, tipo, mensaje):
        if self.activo and bytes(tipo) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(mensaje))
            if msg.message == WM_HOTKEY and msg.wParam == self.id:
                self.al_pulsar()
                return True, 0
        return False, 0
