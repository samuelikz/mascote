from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

ESTILO = """
#cartao { background: white; border-radius: 12px; }
QLabel { color: #222; font: 10pt "Segoe UI"; }
QLabel#titulo { font-weight: bold; }
QLabel#eu { background: #e3f1ff; border-radius: 8px; padding: 4px 8px; }
QLabel#pet { background: #eaf7ef; border-radius: 8px; padding: 4px 8px; }
QPushButton { font: 9pt "Segoe UI"; background: #eaf7ef; border: 1px solid #8fd3a8; border-radius: 9px; padding: 3px 9px; color: #234; }
QPushButton:hover { background: #d4efdd; }
QPushButton#x { border: none; background: transparent; color: #a33; padding: 0 4px; }
QLineEdit { font: 10pt "Segoe UI"; border: 1px solid #ccc; border-radius: 9px; padding: 4px 8px; color: #222; background: white; }
QScrollArea, QScrollArea > QWidget > QWidget { border: none; background: white; }
"""
LARGURA_MAX = 320


class Balao(QWidget):
    escolheu = Signal(object)
    enviou = Signal(str)
    apagar = Signal(object)
    fechou = Signal()

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(ESTILO)
        self.cartao = QFrame(objectName="cartao")
        sombra = QGraphicsDropShadowEffect(blurRadius=16, offset=0, color=QColor(0, 0, 0, 90))
        self.cartao.setGraphicsEffect(sombra)
        fora = QVBoxLayout(self)
        fora.setContentsMargins(10, 10, 10, 10)
        fora.addWidget(self.cartao)
        self.corpo = QVBoxLayout(self.cartao)
        self.corpo.setContentsMargins(12, 10, 12, 10)
        self.corpo.setSpacing(8)
        self.sumir = QTimer(self, singleShot=True, timeout=self.fechar)
        self.pet_geo, self.canto = QRect(), "inf_dir"
        self.modo = ""
        self.chat_lista: QVBoxLayout | None = None
        self.chat_rolagem: QScrollArea | None = None
        self.entrada: QLineEdit | None = None

    # ---- montagem ----
    def _limpar(self, modo: str) -> None:
        self.sumir.stop()
        self.modo = modo
        self.cartao.setMinimumWidth(0)
        self.chat_lista = self.chat_rolagem = self.entrada = None
        while self.corpo.count():
            item = self.corpo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                _apagar_layout(item.layout())

    def _texto(self, texto: str, nome: str = "", selecionavel: bool = False) -> QLabel:
        rotulo = QLabel(texto, objectName=nome, wordWrap=True)
        rotulo.setMaximumWidth(LARGURA_MAX - 24)
        if selecionavel:
            rotulo.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return rotulo

    def _botoes(self, botoes: list[tuple[str, object]]) -> QHBoxLayout:
        linha = QHBoxLayout()
        linha.setSpacing(6)
        for rotulo, valor in botoes:
            b = QPushButton(rotulo, cursor=Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=valor: self.escolheu.emit(v))
            linha.addWidget(b)
        linha.addStretch()
        return linha

    def _mostrar(self, ativar: bool = False) -> None:
        self.cartao.adjustSize()
        self.adjustSize()
        self.posicionar(self.pet_geo, self.canto)
        self.show()
        self.raise_()
        if ativar:
            self.activateWindow()

    # ---- modos ----
    def falar(self, texto: str, botoes: list[tuple[str, object]] = [], ms: int | None = 6000) -> None:
        self._limpar("falar")
        self.corpo.addWidget(self._texto(texto))
        if botoes:
            self.corpo.addLayout(self._botoes(botoes))
        elif ms:
            self.sumir.start(ms)
        self._mostrar()

    def mostrar_resultado(self, texto: str) -> None:
        self._limpar("resultado")
        rolagem = QScrollArea(widgetResizable=True)
        rolagem.setWidget(self._texto(texto, selecionavel=True))
        rolagem.setMaximumHeight(260)
        rolagem.setMinimumWidth(LARGURA_MAX - 24)
        self.corpo.addWidget(rolagem)
        linha = QHBoxLayout()
        copiar = QPushButton("copiar 📋", cursor=Qt.PointingHandCursor)
        copiar.clicked.connect(lambda: (QGuiApplication.clipboard().setText(texto), copiar.setText("copiado! ✅")))
        fechar = QPushButton("fechar", cursor=Qt.PointingHandCursor)
        fechar.clicked.connect(self.fechar)
        linha.addWidget(copiar)
        linha.addWidget(fechar)
        linha.addStretch()
        self.corpo.addLayout(linha)
        self._mostrar()

    def abrir_chat(self, historico: list[dict]) -> None:
        self._limpar("chat")
        conteudo = QWidget()
        self.chat_lista = QVBoxLayout(conteudo)
        self.chat_lista.setContentsMargins(0, 0, 0, 0)
        self.chat_lista.addStretch()
        self.chat_rolagem = QScrollArea(widgetResizable=True)
        self.chat_rolagem.setWidget(conteudo)
        self.chat_rolagem.setFixedSize(LARGURA_MAX - 24, 220)
        self.corpo.addWidget(self.chat_rolagem)
        self.entrada = QLineEdit(placeholderText="fala comigo… (Esc fecha)")
        self.entrada.returnPressed.connect(self._enviar)
        self.corpo.addWidget(self.entrada)
        if not historico:
            self.acrescentar_chat("assistant", "oi! 😄 quer conversar, melhorar uma mensagem ou traduzir algo?")
        for m in historico:
            self.acrescentar_chat(m["role"], m["content"])
        self._mostrar(ativar=True)
        self.entrada.setFocus()

    def acrescentar_chat(self, papel: str, texto: str) -> None:
        if self.chat_lista is None:
            return
        rotulo = self._texto(texto, "eu" if papel == "user" else "pet", selecionavel=True)
        rotulo.setMaximumWidth(LARGURA_MAX - 70)
        linha = QHBoxLayout()
        if papel == "user":
            linha.addStretch()
        linha.addWidget(rotulo)
        if papel != "user":
            linha.addStretch()
        self.chat_lista.addLayout(linha)
        QTimer.singleShot(30, lambda: self.chat_rolagem and self.chat_rolagem.verticalScrollBar().setValue(10**6))

    def _enviar(self) -> None:
        texto = self.entrada.text().strip()
        if texto:
            self.entrada.clear()
            self.acrescentar_chat("user", texto)
            self.enviou.emit(texto)

    def mostrar_lista(self, titulo: str, itens: list[tuple[object, str]]) -> None:
        self._limpar("lista")
        self.cartao.setMinimumWidth(260)
        self.corpo.addWidget(self._texto(titulo, "titulo"))
        if not itens:
            self.corpo.addWidget(self._texto("nada por aqui ainda 🙂"))
        for chave, texto in itens:
            linha = QWidget()
            h = QHBoxLayout(linha)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(self._texto(texto), 1)
            x = QPushButton("✕", objectName="x", cursor=Qt.PointingHandCursor)
            x.clicked.connect(lambda _=False, c=chave, w=linha: (self.apagar.emit(c), w.hide(), self._mostrar()))
            h.addWidget(x)
            self.corpo.addWidget(linha)
        fechar = QPushButton("fechar", cursor=Qt.PointingHandCursor)
        fechar.clicked.connect(self.fechar)
        self.corpo.addWidget(fechar, alignment=Qt.AlignRight)
        self._mostrar()

    def fechar(self) -> None:
        if self.isVisible():
            self.hide()
            self.fechou.emit()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.fechar()
        else:
            super().keyPressEvent(ev)

    # ---- posição ----
    def posicionar(self, pet_geo: QRect, canto: str) -> None:
        self.pet_geo, self.canto = pet_geo, canto
        if pet_geo.isNull():
            return
        tela = QGuiApplication.screenAt(pet_geo.center()) or QGuiApplication.primaryScreen()
        area = tela.availableGeometry()
        x = pet_geo.right() - self.width() if canto.endswith("dir") else pet_geo.left()
        y = pet_geo.top() - self.height() + 18 if canto.startswith("inf") else pet_geo.bottom() - 10
        x = max(area.left(), min(x, area.right() - self.width()))
        y = max(area.top(), min(y, area.bottom() - self.height()))
        self.move(x, y)


def _apagar_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _apagar_layout(item.layout())
    layout.deleteLater()


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    b = Balao()
    area = app.primaryScreen().availableGeometry()
    canto = sys.argv[1] if len(sys.argv) > 1 else "inf_dir"
    pet = QRect(area.right() - 132, area.bottom() - 132, 120, 120) if canto == "inf_dir" else QRect(area.right() - 132, area.top() + 12, 120, 120)
    b.posicionar(pet, canto)
    modos = [
        lambda: b.falar("Nhac! 😋 o que eu faço com isso?", [("lembrar 📌", 1), ("guardar 🧠", 2), ("melhorar ✨", 3), ("traduzir 🌎", 4)]),
        lambda: b.mostrar_resultado("Hi! Could we move the meeting to Friday at 2 pm? Thanks!"),
        lambda: b.abrir_chat([{"role": "user", "content": "oi"}, {"role": "assistant", "content": "oiê! 😄 tudo bem?"}]),
        lambda: b.mostrar_lista("Lembretes ⏰", [(1, "almoço 🍔 todo dia 12:00"), (2, "pagar boleto — 28/10 09:00")]),
    ]
    b.escolheu.connect(lambda v: print("escolheu", v))
    b.enviou.connect(lambda t: print("enviou", t))
    b.apagar.connect(lambda c: print("apagar", c))
    passo = int(sys.argv[2]) if len(sys.argv) > 2 else None
    if passo is not None:
        modos[passo]()
    else:
        fila = list(modos)
        t = QTimer(interval=2500)
        t.timeout.connect(lambda: fila.pop(0)() if fila else app.quit())
        t.start()
        fila.pop(0)()
    sys.exit(app.exec())
