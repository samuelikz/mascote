from datetime import datetime as D

from mascote.agenda import Agenda, proximo_disparo


def test_diario_pula_dias_perdidos():  # Review Focus 3
    assert proximo_disparo(D(2026, 10, 1, 9), {"tipo": "diario"}, D(2026, 10, 20, 15)) == D(2026, 10, 21, 9)


def test_semanal_seg_a_sex_pula_fim_de_semana():
    regra = {"tipo": "semanal", "dias": [0, 1, 2, 3, 4]}
    assert proximo_disparo(D(2026, 10, 30, 9), regra, D(2026, 10, 30, 10)) == D(2026, 11, 2, 9)


def test_mensal_dia_31_em_fevereiro_e_novembro():  # Review Focus 2
    regra = {"tipo": "mensal", "dia": 31}
    assert proximo_disparo(D(2026, 1, 31, 8), regra, D(2026, 2, 1)) == D(2026, 2, 28, 8)
    assert proximo_disparo(D(2026, 1, 31, 8), regra, D(2026, 11, 1)) == D(2026, 11, 30, 8)


def test_feito_unico_apaga_e_repetido_reagenda_uma_vez(tmp_path):
    a = Agenda(tmp_path / "a.db")
    u = a.adicionar("boleto", D(2026, 10, 1, 9))
    r = a.adicionar("remédio", D(2026, 10, 1, 9), {"tipo": "diario"})
    assert {l.id for l in a.vencidos(D(2026, 10, 20, 15))} == {u, r}
    a.feito(u, D(2026, 10, 20, 15))
    a.feito(r, D(2026, 10, 20, 15))
    assert [l.proximo for l in a.listar()] == [D(2026, 10, 21, 9)]
    assert a.vencidos(D(2026, 10, 20, 16)) == []


def test_adiar_mantem_regra(tmp_path):
    a = Agenda(tmp_path / "a.db")
    r = a.adicionar("água", D(2026, 10, 27, 9), {"tipo": "diario"})
    a.adiar(r, D(2026, 10, 27, 9, 1))
    l = a.listar()[0]
    assert l.proximo == D(2026, 10, 27, 9, 11) and l.regra == {"tipo": "diario"}
    a.feito(r, D(2026, 10, 27, 9, 12))
    assert a.listar()[0].proximo == D(2026, 10, 28, 9)


def test_garantir_almoco_idempotente(tmp_path):
    a = Agenda(tmp_path / "a.db")
    a.garantir_almoco()
    a.garantir_almoco()
    assert [(l.texto, l.regra) for l in a.listar()] == [("ALMOCO", {"tipo": "diario"})]


def test_almoco_criado_nao_dispara_na_hora_e_muda_horario(tmp_path):
    a = Agenda(tmp_path / "a.db")
    a.garantir_almoco()
    assert a.vencidos(D.now()) == []
    a.garantir_almoco("12:30")
    l = a.listar()[0]
    assert (l.original.hour, l.original.minute, l.proximo.minute) == (12, 30, 30) and l.proximo > D.now()
