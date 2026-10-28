import math
import random
import time
from typing import Literal

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

Estado = Literal["parado", "pulo", "cochilo", "boca", "pensando", "feliz", "triste", "fome", "chamando"]

COR = QColor("#8fd3a8")
COR_BORDA = QColor("#5fae7c")
TINTA = QColor("#234")
LARGURA, ALTURA = 80, 66  # corpo
OLHOS = [(-15, -38), (15, -38)]  # relativos ao meio da base do corpo
RAIO_OLHO, RAIO_PUPILA = 7.5, 3.6


def pupila(centro: QPointF, mouse: QPointF, raio: float) -> QPointF:
    dx, dy = mouse.x() - centro.x(), mouse.y() - centro.y()
    dist = math.hypot(dx, dy)
    if dist == 0:
        return QPointF(0, 0)
    modulo = min(raio, dist / 20)
    return QPointF(dx / dist * modulo, dy / dist * modulo)


def canto_mais_proximo(pos: QPoint, area: QRect) -> str:
    vertical = "sup" if pos.y() < area.center().y() else "inf"
    horizontal = "esq" if pos.x() < area.center().x() else "dir"
    return f"{vertical}_{horizontal}"


def posicao_do_canto(canto: str, area: QRect, tamanho: QSize, margem: int = 12) -> QPoint:
    x = area.left() + margem if canto.endswith("esq") else area.right() - tamanho.width() - margem
    y = area.top() + margem if canto.startswith("sup") else area.bottom() - tamanho.height() - margem
    return QPoint(x, y)


class Pet(QWidget):
    clicado = Signal()
    clique_direito = Signal(QPoint)
    comeu = Signal(str)
    mudou_canto = Signal(str)

    def __init__(self, canto: str = "inf_dir"):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self.setFixedSize(120, 120)
        self.canto = canto
        self.estado: Estado = "parado"
        self.base: Estado = "parado"  # para onde volta quando um estado com tempo acaba (o app põe "chamando" no lembrete)
        self.estado_ate: float | None = None
        self.pulo_inicio = -10.0
        self.ultimo_pulo = -10.0
        self.piscar_ate = 0.0
        self.proxima_piscada = time.time() + 3
        self.olhar = [QPointF(0, 0), QPointF(0, 0)]
        self.arraste: QPoint | None = None
        self.arrastou = False
        self.encaixar()
        self.relogio = QTimer(self, interval=33, timeout=self.passo)
        self.relogio.start()

    # ---- posição ----
    def area(self) -> QRect:
        tela = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
        return tela.availableGeometry()

    def encaixar(self) -> None:
        self.move(posicao_do_canto(self.canto, self.area(), self.size()))

    def pe(self) -> QPointF:
        """Meio da base do corpo, em coordenadas do widget."""
        return QPointF(self.width() / 2, self.height() - 14)

    # ---- estados ----
    def definir_estado(self, e: Estado, ms: int | None = None) -> None:
        self.estado = e
        self.estado_ate = time.time() + ms / 1000 if ms else None
        if e in ("pulo", "feliz", "chamando"):
            self.pulo_inicio = time.time()
        self.update()

    def voltar(self) -> None:
        self.definir_estado(self.base)

    def pular(self) -> None:
        self.pulo_inicio = time.time()

    def passo(self) -> None:
        if not self.isVisible():
            return  # escondido (tela cheia): nem calcula nem redesenha
        agora = time.time()
        if self.estado_ate and agora >= self.estado_ate:
            self.voltar()
        mouse = QPointF(self.mapFromGlobal(QCursor.pos()))
        b = self.pe()
        alvos = [pupila(QPointF(b.x() + ox, b.y() + oy), mouse, 3.2) for ox, oy in OLHOS]
        self.olhar = [o * 0.65 + a * 0.35 for o, a in zip(self.olhar, alvos)]  # olhos deslizam em vez de pular
        perto = math.hypot(mouse.x() - b.x(), mouse.y() - (b.y() - ALTURA / 2)) < 150
        if self.estado == "cochilo" and perto:
            self.definir_estado("feliz", 1200)  # acordou com o mouse chegando: pulinho de bom dia
        elif self.estado == "parado" and perto and agora - self.ultimo_pulo > 4 and not self.arraste:
            self.ultimo_pulo = self.pulo_inicio = agora
        if self.estado == "chamando" and agora - self.pulo_inicio > 0.9:
            self.pulo_inicio = agora
        if agora >= self.proxima_piscada:
            self.piscar_ate = agora + 0.12
            self.proxima_piscada = agora + random.uniform(2.5, 6)
        self.update()

    def _corpo(self, agora: float) -> tuple[float, float, float]:
        """(deslocamento y, escala x, escala y) com respiração e squash & stretch do pulo."""
        p = (agora - self.pulo_inicio) / 0.5
        if 0 <= p <= 1:
            altura = 22 if self.estado != "chamando" else 16
            sy = 1 + 0.12 * math.sin(math.pi * p) - (0.14 if p < 0.15 or p > 0.85 else 0)
            return -altura * math.sin(math.pi * p), 2 - sy, sy
        if self.estado == "cochilo":
            r = 0.04 * math.sin(agora * 2 * math.pi / 4)
            return 0, 1.06 - r / 2, 0.88 + r
        r = 0.03 * math.sin(agora * 2 * math.pi / 3)
        return 0, 1 - r / 2, 1 + r

    # ---- desenho ----
    def paintEvent(self, _):
        agora = time.time()
        dy, sx, sy = self._corpo(agora)
        b = self.pe()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 50))
        sombra = 1 + dy / 60
        p.drawEllipse(QPointF(b.x(), b.y() + 3), LARGURA / 2 * 0.8 * sombra, 5 * sombra)

        p.translate(b.x(), b.y() + dy)
        p.scale(sx, sy)
        # formato de gota: ponta em cima, barriga redonda embaixo
        meia, ponta = LARGURA / 2, -ALTURA * 1.25
        corpo = QPainterPath(QPointF(0, ponta))
        corpo.cubicTo(meia * 0.25, ponta * 0.8, meia, ponta * 0.55, meia, -ALTURA * 0.38)
        corpo.cubicTo(meia, -ALTURA * 0.08, meia * 0.6, 0, 0, 0)
        corpo.cubicTo(-meia * 0.6, 0, -meia, -ALTURA * 0.08, -meia, -ALTURA * 0.38)
        corpo.cubicTo(-meia, ponta * 0.55, -meia * 0.25, ponta * 0.8, 0, ponta)
        p.setPen(QPen(COR_BORDA, 2))
        p.setBrush(COR)
        p.drawPath(corpo)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 70))
        p.drawEllipse(QPointF(-17, -48), 5, 8)  # brilho
        p.setBrush(QColor(255, 140, 150, 90))
        for ox in (-25, 25):
            p.drawEllipse(QPointF(ox, -24), 6, 3.5)

        e = self.rosto()
        self._olhos(p, agora, e)
        self._boca(p, e)
        self._extras(p, agora, e)
        p.end()

    def rosto(self) -> Estado:
        """Careta desenhada: igual ao estado, menos quando está sendo arrastado (cara de "uou!")."""
        return "boca" if self.arraste is not None and self.arrastou else self.estado

    def _olhos(self, p: QPainter, agora: float, e: Estado) -> None:
        tinta = QPen(TINTA, 2.4, Qt.SolidLine, Qt.RoundCap)
        for i, (ox, oy) in enumerate(OLHOS):
            c = QPointF(ox, oy)
            if e == "cochilo" or (agora < self.piscar_ate and e in ("parado", "fome", "boca")):
                p.setPen(tinta)
                p.drawLine(QPointF(ox - 5, oy + 1), QPointF(ox + 5, oy + 1))
                continue
            if e in ("feliz", "pulo", "chamando"):
                p.setPen(tinta)
                p.setBrush(Qt.NoBrush)
                p.drawArc(QRectF(ox - 6, oy - 3, 12, 10), 0, 180 * 16)
                continue
            p.setPen(Qt.NoPen)
            p.setBrush(Qt.white)
            p.drawEllipse(c, RAIO_OLHO, RAIO_OLHO)
            olhar = {"pensando": QPointF(1.5, -3.5), "triste": QPointF(0, 3)}.get(e, self.olhar[i])
            p.setBrush(TINTA)
            p.drawEllipse(c + olhar, RAIO_PUPILA, RAIO_PUPILA)
            p.setBrush(Qt.white)
            p.drawEllipse(c + olhar + QPointF(-1.2, -1.4), 1.1, 1.1)
            if e == "triste":
                p.setPen(tinta)
                inclina = -4 if ox < 0 else 4
                p.drawLine(QPointF(ox - 6, oy - 10 - inclina / 2), QPointF(ox + 6, oy - 10 + inclina / 2))

    def _boca(self, p: QPainter, e: Estado) -> None:
        p.setPen(QPen(TINTA, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        y = -22
        if e == "boca":
            p.setBrush(QColor("#7a3b4a"))
            p.drawEllipse(QPointF(0, y), 7, 8)
        elif e == "chamando":
            p.setBrush(QColor("#7a3b4a"))
            tri = QPainterPath()
            tri.moveTo(-7, y - 3)
            tri.lineTo(7, y - 3)
            tri.lineTo(0, y + 6)
            tri.closeSubpath()
            p.drawPath(tri)
        elif e in ("feliz", "pulo"):
            p.drawArc(QRectF(-7, y - 7, 14, 12), 200 * 16, 140 * 16)
        elif e == "triste":
            p.drawArc(QRectF(-6, y, 12, 9), 20 * 16, 140 * 16)
        elif e == "fome":
            onda = QPainterPath(QPointF(-8, y))
            for i in range(4):
                onda.quadTo(-6 + i * 4, y + (3 if i % 2 else -3), -4 + i * 4, y)
            p.drawPath(onda)
        elif e == "pensando":
            p.drawLine(QPointF(-4, y + 1), QPointF(4, y))
        elif e == "cochilo":
            p.drawEllipse(QPointF(0, y + 1), 2.5, 2)
        else:
            p.drawArc(QRectF(-5, y - 4, 10, 7), 200 * 16, 140 * 16)

    def _extras(self, p: QPainter, agora: float, e: Estado) -> None:
        p.setPen(TINTA)
        if e == "cochilo":
            f = QFont("Segoe UI", 9, QFont.Bold)
            p.setFont(f)
            sobe = (agora * 8) % 12
            p.drawText(QPointF(26, -58 - sobe), "z")
            p.drawText(QPointF(34, -70 - sobe / 2), "z")
        elif e == "pensando":
            p.setPen(Qt.NoPen)
            p.setBrush(TINTA)
            for i in range(3):
                if int(agora * 3) % 4 > i:
                    p.drawEllipse(QPointF(22 + i * 7, -66), 2, 2)
        elif e == "fome":
            t = (agora % 2) / 2  # a gota escorre e some a cada 2 s
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(124, 198, 255, int(255 * (1 - t))))
            y = 12 * t
            gota = QPainterPath(QPointF(30, -52 + y))
            gota.quadTo(36, -42 + y, 30, -40 + y)
            gota.quadTo(24, -42 + y, 30, -52 + y)
            p.drawPath(gota)
        elif e == "feliz":
            p.setPen(QPen(QColor("#f5b800"), 1.8, Qt.SolidLine, Qt.RoundCap))
            for i, (x, y) in enumerate([(-34, -66), (36, -60), (28, -82)]):
                r = 2 + 2.5 * abs(math.sin(agora * 5 + i * 2))  # brilhinhos piscando em volta
                p.drawLine(QPointF(x - r, y), QPointF(x + r, y))
                p.drawLine(QPointF(x, y - r), QPointF(x, y + r))

    # ---- mouse ----
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.arraste = ev.globalPosition().toPoint() - self.pos()
            self.arrastou = False
        elif ev.button() == Qt.RightButton:
            self.clique_direito.emit(ev.globalPosition().toPoint())

    def mouseMoveEvent(self, ev):
        if self.arraste is not None:
            destino = ev.globalPosition().toPoint() - self.arraste
            if self.arrastou or (destino - self.pos()).manhattanLength() > 5:
                self.arrastou = True
                self.move(destino)

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton or self.arraste is None:
            return
        self.arraste = None
        if not self.arrastou:
            self.pular()
            self.clicado.emit()
            return
        self.arrastou = False
        self.canto = canto_mais_proximo(self.geometry().center(), self.area())
        self.encaixar()
        self.pular()  # quiquinho ao cair no canto
        self.mudou_canto.emit(self.canto)

    # ---- comida ----
    def dragEnterEvent(self, ev):
        if ev.mimeData().hasText():
            ev.acceptProposedAction()
            self.definir_estado("boca")

    def dragLeaveEvent(self, _):
        if self.estado == "boca":
            self.voltar()

    def dropEvent(self, ev):
        texto = ev.mimeData().text().strip()
        ev.acceptProposedAction()
        self.voltar()
        if texto:
            self.comeu.emit(texto)


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication, QMenu

    app = QApplication(sys.argv)
    pet = Pet()
    menu = QMenu()
    for e in Estado.__args__:
        menu.addAction(e, lambda e=e: pet.definir_estado(e, 4000))
    pet.clique_direito.connect(menu.popup)
    pet.comeu.connect(lambda t: print("comeu:", t))
    pet.clicado.connect(lambda: print("clicado"))
    pet.mudou_canto.connect(lambda c: print("canto:", c))
    pet.show()
    if "--estados" in sys.argv:  # percorre os estados sozinho, para conferência visual
        fila = list(Estado.__args__)
        t = QTimer(interval=1500)
        t.timeout.connect(lambda: pet.definir_estado(fila.pop(0)) if fila else app.quit())
        t.start()
    sys.exit(app.exec())
