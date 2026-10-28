"""Desenha a bolinha do pet num .ico (uso: python ferramentas/icone.py saida.ico)."""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from mascote.pet import Pet

app = QApplication(sys.argv)
pet = Pet()
pet.relogio.stop()
pet.piscar_ate = 0
pet.pulo_inicio = -10
imagem = pet.grab().toImage().copy(10, 30, 100, 80)  # recorta o corpo
quadrado = QImage(256, 256, QImage.Format_ARGB32)
quadrado.fill(Qt.transparent)
p = QPainter(quadrado)
p.setRenderHint(QPainter.SmoothPixmapTransform)
p.drawImage(quadrado.rect().adjusted(0, 28, 0, -28), imagem)
p.end()
if not quadrado.save(sys.argv[1]):
    sys.exit("não consegui salvar o ícone")
