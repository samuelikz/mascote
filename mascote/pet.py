import math
import random
import time
from ctypes import wintypes
from typing import Literal

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .janelas import WM_HOTKEY, registrar_atalho

Estado = Literal["parado", "pulo", "cochilo", "boca", "pensando", "feliz", "triste", "fome", "chamando", "foco"]

CORES = {  # nome: (corpo, borda)
    "verde": ("#8fd3a8", "#5fae7c"), "azul": ("#9cc9f5", "#6a9fd6"), "rosa": ("#f5b3cf", "#d6809f"),
    "amarelo": ("#f7dc8a", "#d4b14e"), "roxo": ("#c7b3f2", "#9b84d1"), "dourado": ("#ffd75e", "#c99a1c"),
}
ACESSORIOS = ["nenhum", "chapéu", "laço", "óculos", "cachecol", "coroa"]
PASSEIO_S = 6.0
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
    carinho = Signal()
    moveu = Signal()  # saiu do lugar sem ser arrastado (seguindo a janela onde senta, ou chegou num lugar novo)
    atalho = Signal()  # Ctrl+Alt+M apertado em qualquer programa

    def __init__(self, canto: str = "inf_dir", cor: str = "verde", acessorio: str = "nenhum"):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self.setFixedSize(120, 150)  # folga em cima: pulo + chapéu não cortam
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
        self.passeio: tuple[float, float] | None = None  # (início, distância): vai e volta pela borda da tela
        self.carinho_x: float | None = None  # carinho = mouse indo e voltando em cima dele
        self.carinho_lado = 0
        self.carinho_viradas: list[float] = []
        self.coracoes_ate = 0.0
        self.atalho_ok = False
        # exploração: viagem = (início, origem, destino, duração, altura do arco, onde senta ao chegar)
        self.viagem: tuple | None = None
        self.sentado: tuple[int, int] | None = None  # (janela, distância da borda esquerda dela)
        self.moldura = lambda hwnd: None  # o app diz onde está cada janela (ou None se sumiu)
        self.janela_embaixo = lambda ponto: None  # o app diz se tem janela pra sentar onde ele foi solto
        self.ultimo_seguir = 0.0
        self.vestir(cor, acessorio)
        self.encaixar()
        self.relogio = QTimer(self, interval=33, timeout=self.passo)
        self.relogio.start()

    # ---- posição ----
    def area(self) -> QRect:
        tela = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
        return tela.availableGeometry()

    def encaixar(self) -> None:
        self.move(posicao_do_canto(self.canto, self.area(), self.size()))

    def vestir(self, cor: str, acessorio: str) -> None:
        corpo, borda = CORES.get(cor, CORES["verde"])
        self.cor, self.cor_borda = QColor(corpo), QColor(borda)
        self.acessorio = acessorio if acessorio in ACESSORIOS else "nenhum"
        self.update()

    def fantasma(self, sim: bool) -> None:
        """Modo fantasma: o clique atravessa o pet (desliga pela bandeja)."""
        visivel = self.isVisible()
        self.setWindowFlag(Qt.WindowTransparentForInput, sim)
        if visivel:
            self.show()  # mudar a flag esconde a janela

    def em_casa(self) -> bool:
        return self.viagem is None and self.sentado is None and self.pos() == posicao_do_canto(self.canto, self.area(), self.size())

    def ir_para(self, chao: QPoint, sentar_em: tuple[int, int] | None = None, arco: float | None = None) -> None:
        """Pula em arco até `chao` (onde o pé encosta, em coordenadas da tela)."""
        self.passeio = None
        self.sentado = None
        origem = QPointF(self.pos())
        destino = QPointF(chao.x(), chao.y() - self.pe().y())
        distancia = math.hypot(destino.x() - origem.x(), destino.y() - origem.y())
        if distancia < 2:
            self.sentado = sentar_em
            return
        duracao = min(1.8, 0.45 + distancia / 900)
        arco = min(140, 30 + distancia * 0.25) if arco is None else arco
        self.viagem = (time.time(), origem, destino, duracao, arco, sentar_em)

    def voltar_pra_casa(self) -> None:
        casa = posicao_do_canto(self.canto, self.area(), self.size())
        self.ir_para(QPoint(casa.x(), casa.y() + int(self.pe().y())))

    def cair(self) -> None:
        """A janela onde estava sentado sumiu: cai reto até o chão e depois volta pra casa."""
        self.sentado = None
        chao = self.area().bottom() - 4
        self.ir_para(QPoint(self.x(), chao), sentar_em=(0, 0), arco=0)  # janela 0 = chão

    def _viajar(self, agora: float) -> None:
        inicio, origem, destino, duracao, arco, sentar_em = self.viagem
        t = min(1.0, (agora - inicio) / duracao)
        if arco == 0:
            t_pos = t * t  # caindo: acelera
        else:
            t_pos = t
        x = origem.x() + (destino.x() - origem.x()) * t_pos
        y = origem.y() + (destino.y() - origem.y()) * t_pos - arco * math.sin(math.pi * t)
        self.move(round(x), round(y))
        if t >= 1:
            self.viagem = None
            self.pular()  # aterrissagem com quique
            if sentar_em and sentar_em[0] == 0:  # caiu no chão
                QTimer.singleShot(1200, lambda: self.viagem is None and self.sentado is None and self.voltar_pra_casa())
            else:
                self.sentado = sentar_em
            self.moveu.emit()

    def _seguir_janela(self, agora: float) -> None:
        if agora - self.ultimo_seguir < 0.25:
            return
        self.ultimo_seguir = agora
        hwnd, dx = self.sentado
        r = self.moldura(hwnd)
        if r is None or r.top() - self.area().top() < 100:  # fechou, minimizou ou maximizou: sem lugar pra sentar
            self.cair()
            return
        x = max(r.left(), min(r.left() + dx, r.right() - self.width()))
        destino = QPoint(x, r.top() - int(self.pe().y()))
        if destino != self.pos():
            self.move(destino)
            self.moveu.emit()

    def passear(self) -> None:
        if self.estado == "parado" and self.arraste is None and self.passeio is None and self.em_casa():
            para_dentro = -1 if self.canto.endswith("dir") else 1
            self.passeio = (time.time(), para_dentro * random.uniform(80, 220))

    def parar_passeio(self) -> None:
        if self.passeio is not None:
            self.passeio = None
            self.encaixar()

    def _andar(self, agora: float) -> None:
        inicio, dx = self.passeio
        t = (agora - inicio) / PASSEIO_S
        if t >= 1 or self.estado != "parado":
            self.parar_passeio()
            return
        destino = posicao_do_canto(self.canto, self.area(), self.size())
        self.move(destino.x() + int(dx * math.sin(math.pi * t)), destino.y())

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
        if self.passeio is not None:
            self._andar(agora)
        if self.viagem is not None:
            self._viajar(agora)
        elif self.sentado is not None and self.sentado[0]:
            self._seguir_janela(agora)
        mouse = QPointF(self.mapFromGlobal(QCursor.pos()))
        b = self.pe()
        alvos = [pupila(QPointF(b.x() + ox, b.y() + oy), mouse, 3.2) for ox, oy in OLHOS]
        if self.viagem is not None:  # olha pra onde está pulando
            indo = self.viagem[2] - self.viagem[1]
            alvos = [QPointF(math.copysign(3, indo.x()) if abs(indo.x()) > 5 else 0, 2 if indo.y() > 0 else -2)] * 2
        if self.passeio is not None:  # olha pra onde está andando
            indo = math.cos(math.pi * (agora - self.passeio[0]) / PASSEIO_S) * self.passeio[1]
            alvos = [QPointF(math.copysign(3, indo), 0.5)] * 2
        self.olhar = [o * 0.65 + a * 0.35 for o, a in zip(self.olhar, alvos)]  # olhos deslizam em vez de pular
        perto = math.hypot(mouse.x() - b.x(), mouse.y() - (b.y() - ALTURA / 2)) < 150
        if self.estado == "cochilo" and perto:
            self.definir_estado("feliz", 1200)  # acordou com o mouse chegando: pulinho de bom dia
        elif self.estado == "parado" and perto and agora - self.ultimo_pulo > 4 and not self.arraste:
            self.ultimo_pulo = self.pulo_inicio = agora
        if self.estado == "chamando" and agora - self.pulo_inicio > 0.9:
            self.pulo_inicio = agora
        self._sentir_carinho(mouse, b, agora)
        if agora >= self.proxima_piscada:
            self.piscar_ate = agora + 0.12
            self.proxima_piscada = agora + random.uniform(2.5, 6)
        self.update()

    def _sentir_carinho(self, mouse: QPointF, b: QPointF, agora: float) -> None:
        if not (abs(mouse.x() - b.x()) < LARGURA / 2 and -ALTURA * 1.2 < mouse.y() - b.y() < 0) or self.arraste:
            self.carinho_x = None
            return
        if self.carinho_x is not None and abs(mouse.x() - self.carinho_x) > 3:
            lado = 1 if mouse.x() > self.carinho_x else -1
            if self.carinho_lado and lado != self.carinho_lado:
                self.carinho_viradas.append(agora)
            self.carinho_lado = lado
        if self.carinho_x is None or abs(mouse.x() - self.carinho_x) > 3:
            self.carinho_x = mouse.x()
        self.carinho_viradas = [t for t in self.carinho_viradas if agora - t < 1.5]
        if len(self.carinho_viradas) >= 4 and self.estado not in ("pensando", "chamando"):
            self.carinho_viradas.clear()
            self.coracoes_ate = agora + 2.5
            self.definir_estado("feliz", 2500)
            self.carinho.emit()

    def _corpo(self, agora: float) -> tuple[float, float, float]:
        """(deslocamento y, escala x, escala y) com respiração e squash & stretch do pulo."""
        if self.viagem is not None:  # no ar: esticadinho
            return 0, 0.9, 1.1
        p = (agora - self.pulo_inicio) / 0.5
        if 0 <= p <= 1:
            altura = 22 if self.estado != "chamando" else 16
            sy = 1 + 0.12 * math.sin(math.pi * p) - (0.14 if p < 0.15 or p > 0.85 else 0)
            return -altura * math.sin(math.pi * p), 2 - sy, sy
        if self.passeio is not None:  # passinhos: quica a cada passo
            passo = abs(math.sin(agora * math.pi * 3))
            return -5 * passo, 1 + 0.04 * (1 - passo), 1 - 0.04 * (1 - passo)
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
        if self.sentado is not None and self.sentado[0]:  # pezinhos balançando pra fora da beirada
            p.setPen(QPen(self.cor_borda, 1.5))
            p.setBrush(self.cor)
            for i, ox in enumerate((-13, 13)):
                balanço = 3 * math.sin(agora * 3 + i * math.pi)
                p.drawEllipse(QPointF(ox + balanço, 5), 6, 4.5)
        p.setPen(QPen(self.cor_borda, 2))
        p.setBrush(self.cor)
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
        self._acessorio(p)
        p.end()

    def _acessorio(self, p: QPainter) -> None:
        if self.acessorio == "chapéu":  # chapéu de festa na pontinha
            p.setPen(QPen(QColor("#c0392b"), 1.5))
            p.setBrush(QColor("#ff7a6b"))
            cone = QPainterPath(QPointF(-11, -72))
            cone.lineTo(0, -104)
            cone.lineTo(11, -72)
            cone.quadTo(0, -68, -11, -72)
            p.drawPath(cone)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ffd34d"))
            p.drawEllipse(QPointF(0, -105), 4, 4)
        elif self.acessorio == "laço":
            p.setPen(QPen(QColor("#c2185b"), 1.5))
            p.setBrush(QColor("#ff6fa8"))
            for lado in (-1, 1):
                aba = QPainterPath(QPointF(20, -64))
                aba.lineTo(20 + 11 * lado, -71)
                aba.lineTo(20 + 11 * lado, -57)
                aba.closeSubpath()
                p.drawPath(aba)
            p.drawEllipse(QPointF(20, -64), 3.5, 3.5)
        elif self.acessorio == "óculos":
            p.setPen(QPen(TINTA, 2))
            p.setBrush(QColor(255, 255, 255, 40))
            for ox, oy in OLHOS:
                p.drawEllipse(QPointF(ox, oy), 10, 9)
            p.drawLine(QPointF(-5, -39), QPointF(5, -39))
        elif self.acessorio == "cachecol":
            p.setPen(QPen(QColor("#a12d2d"), 1.2))
            for i, x in enumerate(range(-36, 36, 8)):  # listrado vermelho e branco
                p.setBrush(QColor("#e04848") if i % 2 == 0 else QColor("#fff3f3"))
                p.drawRect(QRectF(x, -13, 8, 8))
            p.setBrush(QColor("#e04848"))
            ponta = QPainterPath(QPointF(16, -6))
            ponta.lineTo(26, 6)
            ponta.lineTo(18, 8)
            ponta.lineTo(10, -6)
            ponta.closeSubpath()
            p.drawPath(ponta)
        elif self.acessorio == "coroa":
            p.setPen(QPen(QColor("#b8860b"), 1.5))
            p.setBrush(QColor("#ffd34d"))
            coroa = QPainterPath(QPointF(-13, -76))
            for x, y in ((-13, -92), (-6, -82), (0, -96), (6, -82), (13, -92), (13, -76)):
                coroa.lineTo(x, y)
            coroa.closeSubpath()
            p.drawPath(coroa)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#e0245e"))
            p.drawEllipse(QPointF(0, -81), 2.5, 2.5)

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
            if e == "foco":  # olhar firme: olho meio fechado e sobrancelha baixa
                p.setPen(Qt.NoPen)
                p.setBrush(Qt.white)
                p.drawEllipse(QPointF(ox, oy + 1.5), RAIO_OLHO, 4.5)
                p.setBrush(TINTA)
                p.drawEllipse(QPointF(ox, oy + 2), 3, 3)
                p.setPen(tinta)
                p.drawLine(QPointF(ox - 7, oy - 5 - (2 if ox < 0 else -2)), QPointF(ox + 7, oy - 5 + (2 if ox < 0 else -2)))
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
        elif e == "foco":
            p.drawLine(QPointF(-4, y), QPointF(4, y))
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
        elif e == "foco":  # faixa na testa, com o nózinho balançando
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#e04848"))
            p.drawRoundedRect(QRectF(-31, -58, 62, 7), 3, 3)
            balanço = 2 * math.sin(agora * 2)
            for dy in (-3, 3):
                fita = QPainterPath(QPointF(30, -55))
                fita.lineTo(42, -55 + dy * 2 + balanço)
                fita.lineTo(40, -55 + dy * 3 + balanço)
                fita.closeSubpath()
                p.drawPath(fita)
        elif e == "fome":
            t = (agora % 2) / 2  # a gota escorre e some a cada 2 s
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(124, 198, 255, int(255 * (1 - t))))
            y = 12 * t
            gota = QPainterPath(QPointF(30, -52 + y))
            gota.quadTo(36, -42 + y, 30, -40 + y)
            gota.quadTo(24, -42 + y, 30, -52 + y)
            p.drawPath(gota)
        elif e == "feliz" and agora < self.coracoes_ate:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ff5c8a"))
            for i, x in enumerate((-30, 32, 0)):
                t = (agora * 0.8 + i * 0.33) % 1  # coraçõezinhos subindo e sumindo
                p.setOpacity(1 - t)
                _coracao(p, QPointF(x + 4 * math.sin(agora * 4 + i), -60 - 30 * t), 5)
            p.setOpacity(1)
        elif e == "feliz":
            p.setPen(QPen(QColor("#f5b800"), 1.8, Qt.SolidLine, Qt.RoundCap))
            for i, (x, y) in enumerate([(-34, -66), (36, -60), (28, -82)]):
                r = 2 + 2.5 * abs(math.sin(agora * 5 + i * 2))  # brilhinhos piscando em volta
                p.drawLine(QPointF(x - r, y), QPointF(x + r, y))
                p.drawLine(QPointF(x, y - r), QPointF(x, y + r))

    # ---- atalho global ----
    def showEvent(self, ev):
        super().showEvent(ev)
        # cada janela nova (o modo fantasma recria) precisa registrar de novo; repetir na mesma não faz mal
        self.atalho_ok = registrar_atalho(int(self.winId())) or self.atalho_ok

    def nativeEvent(self, tipo, mensagem):
        if bytes(tipo) == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(mensagem))
            if msg.message == WM_HOTKEY:
                self.atalho.emit()
                return True, 0
        return super().nativeEvent(tipo, mensagem)

    # ---- mouse ----
    def mousePressEvent(self, ev):
        self.parar_passeio()
        self.viagem = None  # pegou no ar: para onde está
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
                self.sentado = None
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
        pe = self.mapToGlobal(self.pe().toPoint())
        embaixo = self.janela_embaixo(pe)
        if embaixo is not None:  # solto em cima de uma janela: senta nela
            hwnd, r = embaixo
            x = max(r.left(), min(self.x(), r.right() - self.width()))
            self.ir_para(QPoint(x, r.top()), sentar_em=(hwnd, x - r.left()))
            return
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


def _coracao(p: QPainter, c: QPointF, r: float) -> None:
    caminho = QPainterPath(QPointF(c.x(), c.y() + r))
    caminho.cubicTo(c.x() - r * 2, c.y() - r * 0.2, c.x() - r * 0.9, c.y() - r * 1.6, c.x(), c.y() - r * 0.5)
    caminho.cubicTo(c.x() + r * 0.9, c.y() - r * 1.6, c.x() + r * 2, c.y() - r * 0.2, c.x(), c.y() + r)
    p.drawPath(caminho)


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
