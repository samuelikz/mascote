import json
from datetime import datetime

LIMITE = 6000
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

PERSONALIDADE = (
    "Você é o Mascote, um bichinho virtual fofinho e brincalhão que mora no canto da tela do usuário. "
    "Fale em português do Brasil, com frases curtas e emoji, tipo \"ei, bora comer? 🍔\". "
    "Quando o usuário pedir para melhorar ou traduzir um texto, entregue o texto pronto e limpo, "
    "sem gracinha dentro dele. "
    "Se o usuário contar algo duradouro sobre si (nome, horários, gostos, como prefere que você fale), "
    "termine a resposta com uma linha por fato no formato:\nMEMORIA: <fato curto>"
)


def truncar(texto: str) -> str:
    return texto if len(texto) <= LIMITE else texto[:LIMITE] + "…"


def _agora(agora: datetime) -> str:
    return f"Agora é {DIAS[agora.weekday()]}, {agora:%d/%m/%Y %H:%M}."


def _pedido(instrucao: str, texto: str) -> list[dict]:
    return [{"role": "user", "content": f"{instrucao}\n\n{truncar(texto)}"}]


def mensagens_chat(historico: list[dict], memorias: list[str], agora: datetime) -> list[dict]:
    recentes = historico[-12:]
    while recentes and recentes[0]["role"] != "user":  # Gemma exige começar em user
        recentes = recentes[1:]
    if not recentes:
        return []
    lembrancas = "\n".join(f"- {m}" for m in memorias) or "- (nada ainda)"
    cabeca = f"{PERSONALIDADE}\n\n{_agora(agora)}\nO que você lembra do usuário:\n{lembrancas}\n\n---\n\n"
    primeira = {"role": "user", "content": cabeca + truncar(recentes[0]["content"])}
    return [primeira] + [{"role": m["role"], "content": truncar(m["content"])} for m in recentes[1:]]


def mensagens_extrair(texto: str, agora: datetime) -> list[dict]:
    instrucao = (
        f"{_agora(agora)} Transforme o texto abaixo num lembrete. Responda SÓ com JSON, sem explicação:\n"
        '{"texto": "o que lembrar, curto", "quando": "AAAA-MM-DDTHH:MM" ou null se não tiver data/hora, '
        '"repete": null ou {"tipo": "diario"} ou {"tipo": "semanal", "dias": [0-6, 0=segunda]} '
        'ou {"tipo": "mensal", "dia": 1-31}}\n'
        "Se só disser o dia sem hora, use 09:00. \"daqui X minutos\" conta a partir de agora."
    )
    return _pedido(instrucao, texto)


def mensagens_melhorar(texto: str) -> list[dict]:
    return _pedido(
        "Melhore a mensagem abaixo: corrija erros e deixe mais clara e natural, mantendo o sentido, o tom e a língua. "
        "Responda SÓ com a mensagem melhorada, sem comentários.", texto)


def mensagens_traduzir(texto: str) -> list[dict]:
    return _pedido(
        "Traduza o texto abaixo. Se estiver em português, traduza para inglês; senão, para português do Brasil. "
        "Responda SÓ com a tradução, sem comentários.", texto)


def _primeiro_objeto(resposta: str) -> dict | None:
    inicio = resposta.find("{")
    while inicio != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(resposta, inicio)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
        inicio = resposta.find("{", inicio + 1)
    return None


def _regra_valida(r) -> dict | None:
    if not isinstance(r, dict):
        return None
    if r.get("tipo") == "diario":
        return {"tipo": "diario"}
    if r.get("tipo") == "semanal" and isinstance(r.get("dias"), list) and r["dias"] \
            and all(isinstance(d, int) and 0 <= d <= 6 for d in r["dias"]):
        return {"tipo": "semanal", "dias": sorted(set(r["dias"]))}
    if r.get("tipo") == "mensal" and isinstance(r.get("dia"), int) and 1 <= r["dia"] <= 31:
        return {"tipo": "mensal", "dia": r["dia"]}
    return None


def ler_extracao(resposta: str) -> tuple[str, datetime | None, dict | None] | None:
    obj = _primeiro_objeto(resposta)
    if not obj or not isinstance(obj.get("texto"), str) or not obj["texto"].strip():
        return None
    try:
        quando = datetime.fromisoformat(obj.get("quando"))
    except (TypeError, ValueError):
        quando = None
    return obj["texto"].strip(), quando, _regra_valida(obj.get("repete"))


def separar_memoria(resposta: str) -> tuple[str, list[str]]:
    linhas, fatos = [], []
    for linha in resposta.splitlines():
        if linha.strip().upper().startswith("MEMORIA:"):
            fato = linha.split(":", 1)[1].strip()
            if fato:
                fatos.append(fato)
        else:
            linhas.append(linha)
    return "\n".join(linhas).strip(), fatos
