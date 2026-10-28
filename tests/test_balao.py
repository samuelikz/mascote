from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from mascote.balao import Balao

app = QApplication.instance() or QApplication([])


def test_texto_arrastado_aparece_como_texto_e_nao_html():
    b = Balao()
    b.falar("<b>oi</b> <a href='http://x'>link</a>", ms=None)
    b.mostrar_resultado("<i>resultado</i>")
    b.abrir_chat([{"role": "user", "content": "<h1>grande</h1>"}])
    b.mostrar_lista("t", [(1, "<b>item</b>")])
    rotulos = b.findChildren(QLabel)
    assert rotulos and all(r.textFormat() == Qt.PlainText for r in rotulos)
    b.close()


LONGO = "Uma resposta comprida que a Gemma pode dar, com várias frases seguidas pra encher o balão. " * 5  # ~300 px: cabe numa tela normal


def test_resultado_longo_aparece_inteiro_sem_rolar():
    from PySide6.QtWidgets import QScrollArea

    b = Balao()
    b.mostrar_resultado(LONGO)
    app.processEvents()
    rolagem = b.findChild(QScrollArea)
    assert rolagem.verticalScrollBar().maximum() == 0  # cabe na tela: o balão cresce em vez de esconder o texto
    b.close()


def test_chat_cresce_ate_mostrar_a_ultima_resposta():
    b = Balao()
    b.abrir_chat([{"role": "user", "content": "conta algo"}, {"role": "assistant", "content": LONGO}])
    app.processEvents()
    assert b.chat_rolagem.verticalScrollBar().maximum() == 0
    b.close()


def test_texto_curto_nao_fica_espremido():
    b = Balao()
    b.falar('não entendi 😅 tenta pelo chat? tipo "me lembra de X amanhã às 9h"', ms=None)
    app.processEvents()
    rotulo = [r for r in b.findChildren(QLabel) if r.isVisible()][0]
    assert rotulo.width() >= 280
    b.close()
