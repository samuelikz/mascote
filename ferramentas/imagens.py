"""Desenha a bolinha do pet nas imagens do instalador (uso: python ferramentas/imagens.py pasta_saida)."""
import sys
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from mascote.pet import Pet

app = QApplication(sys.argv)
saida = Path(sys.argv[1])
pet = Pet()
pet.relogio.stop()
pet.piscar_ate = 0
pet.pulo_inicio = -10
corpo = pet.grab().toImage().copy(10, 30, 100, 80)  # recorta a bolinha


def desenhar(largura: int, altura: int, fundo: QColor | None, onde: QRect, formato=QImage.Format_RGB32) -> QImage:
    imagem = QImage(largura, altura, formato)
    imagem.fill(fundo if fundo else Qt.transparent)
    p = QPainter(imagem)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(onde, corpo)
    p.end()
    return imagem


salvos = [
    desenhar(256, 256, None, QRect(0, 28, 256, 200), QImage.Format_ARGB32).save(str(saida / "icone.ico")),
    desenhar(493, 58, QColor("white"), QRect(420, 6, 58, 46)).save(str(saida / "banner.bmp")),  # faixa de cima
    desenhar(493, 312, QColor("#eaf7ef"), QRect(22, 110, 120, 96)).save(str(saida / "dialogo.bmp")),  # boas-vindas
]
if not all(salvos):
    sys.exit("não consegui salvar as imagens")
