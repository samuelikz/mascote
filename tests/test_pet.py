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


def test_carinho_e_mouse_indo_e_voltando_em_cima_do_pet():
    from PySide6.QtWidgets import QApplication

    from mascote.pet import Pet

    app = QApplication.instance() or QApplication([])
    pet, sinais = Pet(), []
    pet.carinho.connect(lambda: sinais.append(1))
    b = pet.pe()
    for i in range(12):  # esfrega de um lado pro outro
        pet._sentir_carinho(QPointF(b.x() + (15 if i % 2 else -15), b.y() - 30), b, 100 + i * 0.1)
    assert sinais and pet.estado == "feliz"
    pet.estado, sinais[:] = "parado", []
    for i in range(12):  # passou reto por cima: não é carinho
        pet._sentir_carinho(QPointF(b.x() - 35 + i * 6, b.y() - 30), b, 200 + i * 0.1)
    assert not sinais
    pet.close()
