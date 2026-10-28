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
