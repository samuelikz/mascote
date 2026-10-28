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


def test_fica_pensando_ate_a_ultima_resposta_e_volta_a_chamar(mascote, monkeypatch):
    monkeypatch.setattr(mascote.ia, "pedir", lambda *a, **kw: None)
    mascote.agenda.apagar(mascote.agenda.listar()[0].id)
    mascote.abrir_chat()
    mascote.enviou("oi")
    mascote.enviou("tudo bem?")
    mascote.ia_respondeu("oiê!", ("chat",))
    assert mascote.pet.estado == "pensando"
    mascote.agenda.adicionar("beber água", datetime.now() - timedelta(minutes=1))
    mascote.checar()  # lembrete chega enquanto pensa
    mascote.ia_respondeu("tudo!", ("chat",))
    assert mascote.pet.estado == "chamando"
    mascote.ia_falhou("erro", ("chat",))
    mascote.pet.estado_ate = 0.1  # a cara triste acabou
    mascote.pet.passo()
    assert mascote.pet.estado == "chamando"


def test_resposta_do_chat_reabre_o_balao_se_fechou(mascote, monkeypatch):
    monkeypatch.setattr(mascote.ia, "pedir", lambda *a, **kw: None)
    mascote.agenda.apagar(mascote.agenda.listar()[0].id)
    mascote.abrir_chat()
    mascote.enviou("oi")
    mascote.balao.fechar()
    mascote.ia_respondeu("oiê! 😄", ("chat",))
    assert mascote.balao.modo == "chat" and mascote.balao.isVisible()
    mascote.conversa_nova()
    assert mascote.historico == []


def test_resposta_chega_aos_poucos_sem_mostrar_a_memoria(mascote, monkeypatch):
    from PySide6.QtWidgets import QLabel

    monkeypatch.setattr(mascote.ia, "pedir", lambda *a, **kw: None)
    mascote.agenda.apagar(mascote.agenda.listar()[0].id)
    mascote.abrir_chat()
    mascote.enviou("meu nome é Ana")
    mascote.ia_escrevendo("prazer, A", ("chat",))
    mascote.ia_escrevendo("prazer, Ana! 😄\nMEMO", ("chat",))
    mascote.ia_escrevendo("prazer, Ana! 😄\nMEMORIA: O nome", ("chat",))
    assert mascote.balao.rascunho.text() == "prazer, Ana! 😄"
    mascote.ia_respondeu("prazer, Ana! 😄\nMEMORIA: O nome do usuário é Ana", ("chat",))
    textos = [l.text() for l in mascote.balao.findChildren(QLabel)]
    assert textos.count("prazer, Ana! 😄") == 1 and mascote.balao.rascunho is None


def test_bom_dia_uma_vez_por_dia_e_pausa_depois_de_muito_uso(mascote):
    from PySide6.QtWidgets import QLabel

    mascote.agenda.apagar(mascote.agenda.listar()[0].id)
    mascote.checar()
    assert mascote.balao.findChildren(QLabel)[-1].text().startswith(("bom dia", "boa tarde", "boa noite"))
    mascote.balao.fechar()
    mascote.checar()
    assert not mascote.balao.isVisible()  # já deu bom dia hoje
    mascote.ativo_desde -= modulo_app.PAUSA_S + 1
    mascote.checar()
    assert "pausa" in mascote.balao.findChildren(QLabel)[-1].text()


def test_esconder_segura_o_pet_ate_mandar_aparecer(mascote):
    mascote.checar()
    mascote.escondido = True
    mascote.checar()
    assert not mascote.pet.isVisible()
    mascote.alternar_escondido()
    assert mascote.pet.isVisible() and mascote.balao.modo == "lembrete"


def test_passeio_volta_pro_canto_quando_o_balao_abre(mascote):
    mascote.agenda.apagar(mascote.agenda.listar()[0].id)
    mascote.pet.show()
    canto = mascote.pet.pos()
    mascote.pet.passear()
    mascote.pet.passeio = (mascote.pet.passeio[0] - modulo_app.random.random() - 2, mascote.pet.passeio[1])  # meio do caminho
    mascote.pet.passo()
    assert mascote.pet.pos() != canto
    mascote.abrir_chat()
    assert mascote.pet.pos() == canto and mascote.pet.passeio is None
