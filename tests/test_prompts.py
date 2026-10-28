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
    assert len(msgs[-1]["content"]) < 8000
    assert len(mensagens_extrair("a" * 50_000, AGORA)[-1]["content"]) < 8000


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
