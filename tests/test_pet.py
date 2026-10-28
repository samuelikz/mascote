from PySide6.QtCore import QPoint, QPointF, QRect, Qt

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


def _chegar(pet):
    import time

    while pet.viagem is not None:  # avança o relógio da viagem até o fim
        inicio, *resto = pet.viagem
        pet.viagem = (inicio - 0.5, *resto)
        pet.passo()
        time.sleep(0)


def test_pula_ate_a_janela_senta_segue_ela_e_cai_quando_ela_some():
    from PySide6.QtWidgets import QApplication

    from mascote.pet import Pet

    app = QApplication.instance() or QApplication([])
    pet = Pet()
    pet.show()
    janela = {"r": QRect(300, 400, 800, 500)}
    pet.moldura = lambda hwnd: janela["r"]
    pet.ir_para(QPoint(400, 400), sentar_em=(42, 100))
    assert pet.viagem is not None and not pet.em_casa()
    _chegar(pet)
    assert pet.sentado == (42, 100) and pet.pos() == QPoint(400, 400 - int(pet.pe().y()))
    janela["r"] = QRect(500, 450, 800, 500)  # arrastaram a janela
    pet.ultimo_seguir = 0
    pet.passo()
    assert pet.pos() == QPoint(600, 450 - int(pet.pe().y()))
    janela["r"] = None  # fechou
    pet.ultimo_seguir = 0
    pet.passo()
    assert pet.sentado is None and pet.viagem is not None  # caindo
    _chegar(pet)
    assert pet.y() + pet.pe().y() >= pet.area().bottom() - 5  # chegou no chão
    pet.voltar_pra_casa()
    _chegar(pet)
    assert pet.em_casa()
    pet.close()


def test_solto_em_cima_de_janela_senta_nela():
    from PySide6.QtCore import QPointF as P
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    from mascote.pet import Pet

    app = QApplication.instance() or QApplication([])
    pet = Pet()
    pet.show()
    r = QRect(200, 300, 900, 500)
    pet.janela_embaixo = lambda pe: (7, r)
    pet.moldura = lambda hwnd: r
    pet.arraste, pet.arrastou = QPoint(10, 10), True
    pet.move(500, 300 - int(pet.pe().y()) - 10)
    soltar = QMouseEvent(QMouseEvent.MouseButtonRelease, P(10, 10), P(10, 10), Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
    pet.mouseReleaseEvent(soltar)
    _chegar(pet)
    assert pet.sentado == (7, 500 - 200) and pet.y() == 300 - int(pet.pe().y())
    pet.close()
