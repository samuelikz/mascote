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
