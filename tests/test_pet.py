from PySide6.QtCore import QPoint, QPointF, QRect

from mascote.pet import canto_mais_proximo, pupila


def test_pupila_limitada_ao_raio():
    p = pupila(QPointF(0, 0), QPointF(1000, 0), 4)
    assert abs(p.x() - 4) < 1e-6 and p.y() == 0
    assert pupila(QPointF(0, 0), QPointF(0, 0), 4) == QPointF(0, 0)


def test_canto_mais_proximo():
    area = QRect(0, 0, 1920, 1040)
    assert canto_mais_proximo(QPoint(1800, 900), area) == "inf_dir"
    assert canto_mais_proximo(QPoint(10, 10), area) == "sup_esq"
