from datetime import date

from mascote import diario

HOJE = date(2026, 10, 28)


def test_registrar_soma_pontos_e_avisa_quando_sobe_de_nivel():
    cfg = {}
    assert diario.nivel(cfg)[:2] == (0, "conhecidos")
    subidas = [diario.registrar(cfg, "focos", HOJE) for _ in range(4)]  # 5 pontos cada
    assert cfg["amizade"] == 20 and subidas == [False, False, False, True]
    assert diario.nivel(cfg)[1] == "colegas" and diario.nivel(cfg)[3] == 40
    assert cfg["diario"]["2026-10-28"] == {"focos": 4}


def test_semana_soma_so_os_ultimos_7_dias_e_esquece_o_muito_velho():
    cfg = {}
    diario.registrar(cfg, "lembretes", date(2026, 10, 1))
    diario.registrar(cfg, "lembretes", date(2026, 10, 22))  # 7º dia contando de trás: entra
    diario.registrar(cfg, "carinhos", HOJE)
    assert diario.semana(cfg, HOJE) == {"lembretes": 1, "focos": 0, "comidas": 0, "carinhos": 1, "conversas": 0}
    assert diario.descrever_semana(diario.semana(cfg, HOJE)) == "✅ 1 lembretes · 🥰 1 carinhos"
    diario.registrar(cfg, "carinhos", date(2027, 1, 1))
    assert "2026-10-01" not in cfg["diario"]  # mais de 60 dias: apagado
    assert diario.descrever_semana(dict.fromkeys(diario.PONTOS, 0)).startswith("nada ainda")


def test_premios_liberam_por_nivel():
    cfg = {"amizade": 60}  # amigos (nível 2)
    assert diario.liberado(cfg, "cachecol") and not diario.liberado(cfg, "coroa")
    assert diario.liberado(cfg, "chapéu")  # o que não é prêmio está sempre liberado
