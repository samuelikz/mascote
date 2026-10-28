import ctypes

ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
from ctypes import wintypes

QUNS_TELA_CHEIA = {2, 3, 4}  # BUSY, RUNNING_D3D_FULL_SCREEN, PRESENTATION_MODE
WM_HOTKEY = 0x0312
ATALHO = "Ctrl+Alt+M"
_MOD_ALT, _MOD_CONTROL, _MOD_NOREPEAT = 0x1, 0x2, 0x4000


def registrar_atalho(hwnd: int) -> bool:
    """Ctrl+Alt+M em qualquer programa vira WM_HOTKEY nesta janela. False se outro programa já usa o atalho."""
    try:
        return bool(ctypes.windll.user32.RegisterHotKey(
            ctypes.c_void_p(hwnd), 1, _MOD_ALT | _MOD_CONTROL | _MOD_NOREPEAT, ord("M")))
    except (OSError, AttributeError):
        return False


def administrador() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (OSError, AttributeError):
        return False


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
