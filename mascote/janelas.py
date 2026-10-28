import ctypes

ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
from ctypes import wintypes

QUNS_TELA_CHEIA = {2, 3, 4}  # BUSY, RUNNING_D3D_FULL_SCREEN, PRESENTATION_MODE


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def tela_cheia() -> bool:
    try:
        estado = ctypes.c_int()
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(estado)) != 0:
            return False
        return estado.value in QUNS_TELA_CHEIA
    except (OSError, AttributeError):
        return False


def segundos_ocioso() -> float:
    try:
        info = _LASTINPUTINFO(ctypes.sizeof(_LASTINPUTINFO), 0)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        agora = ctypes.windll.kernel32.GetTickCount64() & 0xFFFFFFFF  # dwTime é 32 bits
        return ((agora - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except (OSError, AttributeError):
        return 0.0
