"""Onde o pet pode sentar: borda de cima das janelas abertas e ícones da área de trabalho.

O Windows fala em pixels físicos; o Qt, em pixels lógicos (com escala de tela). Tudo que sai daqui já é lógico.
Os ícones vêm do ListView da área de trabalho (processo do Explorer): só LÊ a memória de lá, nunca escreve.
"""
import ctypes
import os
import random
from ctypes import wintypes

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QGuiApplication

user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowExW.restype = wintypes.HWND
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

GA_ROOT, GW_OWNER, WS_EX_TOOLWINDOW, GWL_EXSTYLE = 2, 4, 0x80, -20
DWMWA_EXTENDED_FRAME_BOUNDS, DWMWA_CLOAKED = 9, 14
LVM_GETITEMCOUNT, LVM_GETITEMPOSITION, LVM_GETITEMSPACING = 0x1004, 0x1010, 0x1033
IGNORAR = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Windows.UI.Core.CoreWindow"}
AREA_DE_TRABALHO = {"Progman", "WorkerW", "SHELLDLL_DefView", "SysListView32"}
BOTOES_DA_JANELA = 160  # minimizar/maximizar/fechar ficam à direita: o pet não senta em cima deles


def para_qt(x: int, y: int) -> QPoint:
    """Pixel físico → lógico. O Qt mantém o canto de cada tela igual nos dois e escala o resto."""
    for tela in QGuiApplication.screens():
        g, escala = tela.geometry(), tela.devicePixelRatio()
        if g.x() <= x < g.x() + g.width() * escala and g.y() <= y < g.y() + g.height() * escala:
            return QPoint(round(g.x() + (x - g.x()) / escala), round(g.y() + (y - g.y()) / escala))
    return QPoint(x, y)


def para_nativo(p: QPoint) -> wintypes.POINT:
    tela = QGuiApplication.screenAt(p) or QGuiApplication.primaryScreen()
    g, escala = tela.geometry(), tela.devicePixelRatio()
    return wintypes.POINT(round(g.x() + (p.x() - g.x()) * escala), round(g.y() + (p.y() - g.y()) * escala))


def _classe(hwnd) -> str:
    nome = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, nome, 64)
    return nome.value


def _meu(hwnd) -> bool:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid()


def _escondida(hwnd) -> bool:
    oculta = ctypes.c_int()  # janelas de app da loja "escondidas" continuam visíveis pro EnumWindows
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(oculta), ctypes.sizeof(oculta))
    return bool(oculta.value)


def moldura(hwnd) -> QRect | None:
    """Retângulo visível da janela (sem a sombra invisível do Windows 10/11), ou None se sumiu/minimizou."""
    if not hwnd or not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd) or _escondida(hwnd):
        return None
    r = wintypes.RECT()
    if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)):
        user32.GetWindowRect(hwnd, ctypes.byref(r))
    a, b = para_qt(r.left, r.top), para_qt(r.right, r.bottom)
    return QRect(a, b).adjusted(0, 0, -1, -1)


def janelas() -> list[tuple[int, QRect]]:
    achadas = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cada(hwnd, _):
        if (user32.GetWindowTextLengthW(hwnd) and not user32.GetWindow(hwnd, GW_OWNER)
                and not user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW
                and _classe(hwnd) not in IGNORAR and not _meu(hwnd)):
            r = moldura(hwnd)
            if r is not None:
                achadas.append((hwnd, r))
        return True

    user32.EnumWindows(cada, 0)
    return achadas


def _quem_aparece_em(p: QPoint) -> int:
    return user32.GetAncestor(user32.WindowFromPoint(para_nativo(p)), GA_ROOT) or 0


def borda_visivel(hwnd: int, p: QPoint) -> bool:
    """Nesse ponto da borda aparece mesmo esta janela (não outra por cima)? O próprio pet não conta."""
    quem = _quem_aparece_em(p)
    return quem == hwnd or (quem and _meu(quem))


def _lista_da_area_de_trabalho() -> int:
    vista = user32.FindWindowExW(user32.FindWindowW("Progman", None), None, "SHELLDLL_DefView", None)
    trabalhador = None
    while not vista:  # com alguns papéis de parede a área de trabalho mora num WorkerW
        trabalhador = user32.FindWindowExW(None, trabalhador, "WorkerW", None)
        if not trabalhador:
            return 0
        vista = user32.FindWindowExW(trabalhador, None, "SHELLDLL_DefView", None)
    return user32.FindWindowExW(vista, None, "SysListView32", None) or 0


def icones() -> list[QRect]:
    """Retângulos dos ícones da área de trabalho que estão à mostra (não tampados por janelas)."""
    lista = _lista_da_area_de_trabalho()
    if not lista:
        return []
    total = min(user32.SendMessageW(lista, LVM_GETITEMCOUNT, 0, 0), 200)
    espaco = user32.SendMessageW(lista, LVM_GETITEMSPACING, 0, 0)
    largura, altura = espaco & 0xFFFF, (espaco >> 16) & 0xFFFF
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(lista, ctypes.byref(pid))
    processo = kernel32.OpenProcess(0x0008 | 0x0010, False, pid.value)  # VM_OPERATION | VM_READ: só leitura
    if not processo:
        return []
    achados = []
    try:
        memoria = kernel32.VirtualAllocEx(processo, None, ctypes.sizeof(wintypes.POINT), 0x1000, 0x04)
        if not memoria:
            return []
        try:
            for i in range(total):
                ponto = wintypes.POINT()
                user32.SendMessageW(lista, LVM_GETITEMPOSITION, i, memoria)
                if kernel32.ReadProcessMemory(processo, memoria, ctypes.byref(ponto), ctypes.sizeof(ponto), None):
                    user32.ClientToScreen(lista, ctypes.byref(ponto))
                    a, b = para_qt(ponto.x, ponto.y), para_qt(ponto.x + largura, ponto.y + altura)
                    r = QRect(a, b)
                    if _classe(_quem_aparece_em(r.center())) in AREA_DE_TRABALHO:
                        achados.append(r)
        finally:
            kernel32.VirtualFreeEx(processo, memoria, 0, 0x8000)
    finally:
        kernel32.CloseHandle(processo)
    return achados


def lugares(largura_pet: int, area: QRect, folga_em_cima: int) -> list[tuple[QPoint, int | None]]:
    """Pontos onde o pé do pet pode encostar: (x da esquerda do pet, y da superfície), hwnd da janela ou None."""
    achados = []
    for hwnd, r in janelas():
        espaco = r.width() - BOTOES_DA_JANELA - largura_pet - 30
        if espaco < 40 or r.height() < 150 or r.top() - area.top() < folga_em_cima or not area.intersects(r):
            continue
        x = r.left() + 30 + random.randint(0, espaco)
        if borda_visivel(hwnd, QPoint(x + largura_pet // 2, r.top() + 3)):
            achados.append((QPoint(x, r.top()), hwnd))
    for r in icones():
        if r.top() - area.top() >= folga_em_cima and area.contains(r.center()):
            achados.append((QPoint(r.center().x() - largura_pet // 2, r.top() + 6), None))
    return achados


def janela_embaixo(ponto: QPoint, largura_pet: int, tolerancia: int = 40) -> tuple[int, QRect] | None:
    """Janela cuja borda de cima está logo abaixo do pé do pet (pra sentar quando ele é solto ali)."""
    for hwnd, r in janelas():
        if (r.left() <= ponto.x() <= r.right() - BOTOES_DA_JANELA and abs(r.top() - ponto.y()) <= tolerancia
                and borda_visivel(hwnd, QPoint(ponto.x(), r.top() + 3))):
            return hwnd, r
    return None
