import threading
import time
from datetime import datetime, timedelta

import pytest
from PySide6.QtWidgets import QApplication

from mascote import app as modulo_app

qt = QApplication.instance() or QApplication([])


@pytest.fixture
def mascote(monkeypatch):
    tela = {"cheia": False}
    monkeypatch.setattr(modulo_app, "tela_cheia", lambda: tela["cheia"])
    monkeypatch.setattr(modulo_app, "segundos_ocioso", lambda: 0.0)
    m = modulo_app.App()
    m.agenda.adicionar("pagar boleto", datetime.now() - timedelta(minutes=1))
    m.tela = tela
    yield m
    m.balao.close()
    m.pet.close()


def test_lembrete_volta_depois_de_comida_menu_ou_tela_cheia(mascote):  # revisão #1
    mascote.checar()
    assert mascote.balao.modo == "lembrete"
    mascote.comeu("um texto")  # comida tampa o balão do lembrete
    mascote.checar()
    assert mascote.balao.modo == "lembrete"
    mascote.ver_memorias()  # menu tampa
    mascote.checar()
    assert mascote.balao.modo == "lembrete"
    mascote.tela["cheia"] = True
    mascote.checar()
    mascote.tela["cheia"] = False
    mascote.checar()
    assert mascote.balao.modo == "lembrete" and mascote.balao.isVisible()


def test_chat_aberto_nao_segura_lembrete(mascote):  # revisão #2
    mascote.abrir_chat()
    mascote.checar()
    assert mascote.balao.modo == "lembrete"


def test_fechar_chat_cancela_pra_quando(mascote):  # revisão #5
    mascote.agenda.apagar(mascote.agenda.listar()[0].id)
    mascote.esperando_quando = "ligar pro dentista"
    mascote.abrir_chat()
    mascote.balao.fechar()
    assert mascote.esperando_quando == ""


def test_pra_quando_abre_chat_sem_roubar_foco(mascote, monkeypatch):  # revisão #11
    chamadas = []
    monkeypatch.setattr(mascote.balao, "abrir_chat", lambda h, ativar=True: chamadas.append(ativar))
    mascote.salvar_lembrete('{"texto":"ligar pro dentista","quando":null}', "ligar pro dentista")
    assert chamadas == [False]


def test_resultado_tem_espaco_para_texto_longo():  # revisão #4
    assert modulo_app.parametros("resultado")[1] >= 2048
    assert modulo_app.parametros("lembrar")[0] <= 0.2


def test_erro_inesperado_na_ia_vira_falhou():  # revisão #6
    from mascote.ia import PonteIA

    class Quebrado:
        def perguntar(self, *a):
            raise OSError("acesso negado")

    ponte, falhas, pronto = PonteIA(Quebrado()), [], threading.Event()
    ponte.falhou.connect(lambda erro, etiqueta: (falhas.append(erro), pronto.set()))
    ponte.pedir([], ("chat",))
    fim = time.time() + 5
    while not pronto.is_set() and time.time() < fim:  # o sinal chega pela fila de eventos do Qt
        qt.processEvents()
        time.sleep(0.02)
    assert pronto.is_set() and "acesso negado" in falhas[0]


def test_app_usa_nome_e_ia_das_preferencias(monkeypatch):
    from mascote import config
    from mascote.ia import ClienteOllama

    config.salvar_preferencia("Nome", "Bolinha")
    config.salvar_preferencia("IA", "ollama")
    monkeypatch.setattr(modulo_app, "tela_cheia", lambda: False)
    m = modulo_app.App()
    pedidos = []
    monkeypatch.setattr(m.ia, "pedir", lambda msgs, etiqueta, **kw: pedidos.append(msgs))
    m.enviou("oi")
    assert isinstance(m.servidor, ClienteOllama)
    assert "Bolinha" in pedidos[0][0]["content"]
    m.ia_falhou("não achei o Ollama: recusado", ("chat",))
    from PySide6.QtWidgets import QLabel

    assert "Ollama" in m.balao.findChildren(QLabel)[-1].text()
    m.balao.close()
    m.pet.close()


def test_engolir_so_come_e_avisa(mascote):
    from PySide6.QtWidgets import QLabel, QPushButton

    mascote.agenda.apagar(mascote.agenda.listar()[0].id)
    mascote.comeu("um textão qualquer")
    assert any(b.text().startswith("engolir") for b in mascote.balao.findChildren(QPushButton))
    lembretes, memorias = len(mascote.agenda.listar()), len(modulo_app.memoria.listar())
    mascote.escolheu(("comida", "engolir"))
    assert "engoli todo o texto" in mascote.balao.findChildren(QLabel)[-1].text()
    assert (len(mascote.agenda.listar()), len(modulo_app.memoria.listar())) == (lembretes, memorias)
