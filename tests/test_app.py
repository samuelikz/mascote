from datetime import datetime

from mascote.agenda import Lembrete
from mascote.app import escolher_fala_lembrete


def test_fala_do_almoco_e_lembrete():
    D = datetime(2026, 10, 27, 12)
    assert escolher_fala_lembrete(Lembrete(1, "ALMOCO", D, D, {"tipo": "diario"})) == "ei, bora comer? 🍔"
    assert escolher_fala_lembrete(Lembrete(2, "pagar boleto", D, D, None)) == "ei! hora de pagar boleto 💡"


def test_descrever_quando():
    from mascote.app import descrever_quando

    agora = datetime(2026, 10, 27, 22, 0)  # terça
    assert descrever_quando(datetime(2026, 10, 28, 9), None, agora) == "amanhã às 9h"
    assert descrever_quando(datetime(2026, 10, 27, 23, 30), None, agora) == "hoje às 23h30"
    assert descrever_quando(datetime(2026, 10, 30, 14), None, agora) == "sexta às 14h"
    assert descrever_quando(datetime(2026, 11, 20, 8), None, agora) == "20/11 às 8h"
    assert descrever_quando(datetime(2026, 10, 28, 9), {"tipo": "diario"}, agora) == "todo dia às 9h"
    assert descrever_quando(datetime(2026, 11, 2, 7), {"tipo": "semanal", "dias": [0]}, agora) == "toda segunda às 7h"
    assert descrever_quando(datetime(2026, 11, 1, 7), {"tipo": "semanal", "dias": [6]}, agora) == "todo domingo às 7h"
    assert descrever_quando(datetime(2026, 10, 28, 7), {"tipo": "semanal", "dias": [0, 1, 2, 3, 4]}, agora) == "de segunda a sexta às 7h"
    assert descrever_quando(datetime(2026, 10, 28, 7), {"tipo": "semanal", "dias": [0, 2, 4]}, agora) == "toda seg, qua e sex às 7h"
    assert descrever_quando(datetime(2026, 11, 5, 8), {"tipo": "mensal", "dia": 5}, agora) == "todo dia 5 às 8h"


def test_quando_no_passado_vira_futuro_ou_pergunta():
    from mascote.app import ajustar_quando

    agora = datetime(2026, 10, 27, 22, 0)
    assert ajustar_quando(datetime(2026, 10, 27, 9), None, agora) is None
    assert ajustar_quando(datetime(2026, 10, 27, 9), {"tipo": "diario"}, agora) == datetime(2026, 10, 28, 9)
    assert ajustar_quando(datetime(2026, 10, 28, 9), None, agora) == datetime(2026, 10, 28, 9)


def test_repetido_comeca_no_primeiro_dia_valido_da_regra():
    from mascote.app import ajustar_quando

    agora = datetime(2026, 10, 27, 22, 0)  # terça
    assert ajustar_quando(datetime(2026, 10, 28, 9), {"tipo": "semanal", "dias": [4]}, agora) == datetime(2026, 10, 30, 9)


def test_saudacao_e_filtro_de_traducao():
    from mascote.app import ofertas, saudacao, sem_emoji

    assert saudacao(datetime(2026, 10, 28, 8), ["almoço às 12h"]) == "bom dia! ☀️ hoje tem: almoço às 12h"
    assert saudacao(datetime(2026, 10, 28, 20), []).startswith("boa noite!")
    assert ofertas("Could we move the meeting to Friday afternoon?") == ["traduzir"]
    assert ofertas("você pode mudar a reunião pra sexta?") == []
    assert ofertas("https://github.com/samuelikz/mascote/releases") == []
    assert ofertas("for (int i = 0; i < n; i++) { total += i; }") == []
    textao = "o projeto vai bem e a equipe entregou tudo no prazo, então agora " * 10
    assert ofertas(textao) == ["resumir"]
    assert ofertas("we shipped everything on time and the team is happy with it now " * 10) == ["traduzir", "resumir"]
    assert sem_emoji("eba! ✅ bora 🍔") == "eba!  bora"


def test_resposta_pronta_nunca_passa_da_metade_do_contexto():
    from mascote.app import parametros

    assert parametros("resultado", 4096)[1] == 2048 and parametros("resultado", 8192)[1] == 4096
