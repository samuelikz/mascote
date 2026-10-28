from datetime import datetime

from mascote.prompts import ler_extracao, mensagens_chat, mensagens_extrair, mensagens_melhorar, separar_memoria

AGORA = datetime(2026, 10, 27, 22, 0)


def test_extracao_com_cercas_e_texto_em_volta():  # Review Focus 1
    r = 'Claro! ```json\n{"texto":"pagar boleto","quando":"2026-10-28T09:00","repete":null}\n``` 😊'
    assert ler_extracao(r) == ("pagar boleto", datetime(2026, 10, 28, 9, 0), None)


def test_extracao_quebrada_ou_sem_hora():
    assert ler_extracao("não entendi 😅") is None
    assert ler_extracao('{"texto": "x", "quando": ') is None
    assert ler_extracao('{"texto":"ligar","quando":"sexta","repete":{"tipo":"anual"}}') == ("ligar", None, None)


def test_extracao_semanal():
    r = '{"texto":"academia","quando":"2026-10-28T07:00","repete":{"tipo":"semanal","dias":[0,2,4]}}'
    assert ler_extracao(r)[2] == {"tipo": "semanal", "dias": [0, 2, 4]}


def test_texto_gigante_truncado():  # Review Focus 5
    msgs = mensagens_melhorar("a" * 50_000)
    assert len(msgs[-1]["content"]) < 12000  # LIMITE cabe no contexto 8192 com a resposta
    assert len(mensagens_extrair("a" * 50_000, AGORA)[-1]["content"]) < 12000


def test_chat_sem_role_system_e_com_memorias():
    msgs = mensagens_chat([{"role": "user", "content": "oi"}], ["Meu nome é Samuel"], AGORA)
    assert all(m["role"] != "system" for m in msgs)
    assert "Meu nome é Samuel" in msgs[0]["content"] and msgs[0]["content"].endswith("oi")


def test_chat_historico_longo_comeca_em_user():
    hist = [{"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(31)]
    msgs = mensagens_chat(hist, [], AGORA)
    assert len(msgs) <= 12 and msgs[0]["role"] == "user" and msgs[-1]["content"] == "30"


def test_separar_memoria():
    assert separar_memoria("Prazer, Samuel! 😄\nMEMORIA: nome é Samuel") == ("Prazer, Samuel! 😄", ["nome é Samuel"])


def test_extracao_dias_por_nome():
    r = '{"texto":"academia","quando":"2026-10-28T07:00","repete":{"tipo":"semanal","dias":["seg","Qua","sexta-feira"]}}'
    assert ler_extracao(r)[2] == {"tipo": "semanal", "dias": [0, 2, 4]}
    r = '{"texto":"feira","quando":"2026-10-31T08:00","repete":{"tipo":"semanal","dias":["sáb","dom"]}}'
    assert ler_extracao(r)[2] == {"tipo": "semanal", "dias": [5, 6]}


def test_conferir_extracao_descarta_data_e_repeticao_inventadas():
    from mascote.prompts import conferir_extracao

    quando, regra = datetime(2026, 11, 6, 9), {"tipo": "semanal", "dias": [3]}
    assert conferir_extracao("ligar pro dentista", quando, regra) == (None, None)
    assert conferir_extracao("ligar pro dentista sexta", quando, regra) == (quando, None)
    assert conferir_extracao("academia toda segunda às 7h", quando, regra) == (quando, regra)
    assert conferir_extracao("tomar remédio todo dia 8h", quando, {"tipo": "diario"}) == (quando, {"tipo": "diario"})
    assert conferir_extracao("beber água daqui 2 minutos", quando, None) == (quando, None)
    assert conferir_extracao("reunião amanhã", quando, None) == (quando, None)
    assert conferir_extracao("pagar boleto 28/10", quando, None) == (quando, None)


def test_traducao_decide_a_lingua_no_codigo():
    from mascote.prompts import mensagens_traduzir, parece_portugues

    assert parece_portugues("oi tudo bem queria saber se vc pode mandar o relatorio")
    assert parece_portugues("Não sei se você vai conseguir")
    assert not parece_portugues("Hi team, the deploy was moved to Thursday because of the database migration.")
    assert not parece_portugues("Hola, ¿cómo estás? Quiero saber si puedes venir mañana.")
    assert "para inglês" in mensagens_traduzir("oi, tudo bem com você?")[0]["content"]
    assert "para português" in mensagens_traduzir("Hi team, how are you?")[0]["content"]


def test_extrair_traz_calendario_dos_proximos_dias():
    conteudo = mensagens_extrair("sexta às 15h", AGORA)[0]["content"]  # AGORA = terça 27/10
    assert "sexta-feira 30/10" in conteudo and "quarta-feira 28/10" in conteudo


def test_extracao_tira_me_lembra_do_texto():
    assert ler_extracao('{"texto":"Me lembra de ir na academia","quando":null}')[0] == "ir na academia"


def test_quando_com_fuso_vira_hora_local_sem_fuso():  # revisão #7
    assert ler_extracao('{"texto":"x","quando":"2026-10-28T09:00-03:00"}')[1].tzinfo is None


def test_chat_cabe_no_contexto_mesmo_com_memorias_e_historico_enormes():  # revisão #3
    hist = [{"role": "user" if i % 2 == 0 else "assistant", "content": "a" * 6000} for i in range(11)]
    msgs = mensagens_chat(hist, ["m" * 6000] * 10, AGORA)
    assert sum(len(m["content"]) for m in msgs) <= 24000  # ~6500 tokens: cabe no contexto 8192
    assert msgs[0]["role"] == "user" and msgs[-1]["role"] == "user" and msgs[-1]["content"].endswith("a" * 6000)


def test_chat_usa_o_nome_escolhido_no_instalador():
    msgs = mensagens_chat([{"role": "user", "content": "qual seu nome?"}], [], AGORA, nome="Bolinha")
    assert "Você é o Bolinha" in msgs[0]["content"] and "Mascote" not in msgs[0]["content"]


def test_memorias_relevantes_vem_primeiro_e_cabem_no_limite():
    from mascote.prompts import escolher_memorias

    memorias = [f"fato velho {i} " + "x" * 90 for i in range(50)] + ["O usuário trabalha com Python"]
    escolhidas = escolher_memorias(memorias, "me ajuda com um erro em python", limite=300)
    assert "O usuário trabalha com Python" in escolhidas
    assert sum(map(len, escolhidas)) <= 300
    assert escolher_memorias(["a", "b"], "") == ["a", "b"]  # ordem original
