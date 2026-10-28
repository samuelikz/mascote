import json
import re
import unicodedata
from datetime import datetime, timedelta

LIMITE = 6000
ORCAMENTO = 9000  # caracteres por pedido de chat (~2300 tokens): cabe no contexto 4096 com folga pra resposta
LIMITE_MEMORIAS = 2000
SIGLAS = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
PALAVRAS_PT = set(
    "não nao você voce vc pra com tudo oi olá ola está tá eu meu minha isso muito obrigado obrigada também tambem "
    "um uma é ou mas sim quero queria pode bom boa então entao aqui agora gente vou vai ser tem".split()
)
TEMPO = re.compile(
    r"\d|hoje|amanh|segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo|semana|m[eê]s|daqui|manh[aã]|tarde|noite"
    r"|meio[- ]dia|meia[- ]noite|hora|minuto|\bdia\b|janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto"
    r"|setembro|outubro|novembro|dezembro", re.IGNORECASE)
REPETICAO = re.compile(
    r"\btod[oa]s?\b|\bcada\b|diariamente|sempre|semanalmente|mensalmente|de segunda a sexta|dias [uú]teis", re.IGNORECASE)
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

PERSONALIDADE = (
    "Você é o Mascote, um bichinho virtual fofinho e brincalhão que mora no canto da tela do usuário. "
    "Fale em português do Brasil, com frases curtas e emoji, tipo \"ei, bora comer? 🍔\". "
    "Quando o usuário pedir para melhorar ou traduzir um texto, entregue o texto pronto e limpo, "
    "sem gracinha dentro dele. "
    "Se o usuário contar algo duradouro sobre si (nome, horários, gostos, como prefere que você fale), "
    "termine a resposta com uma linha por fato no formato:\nMEMORIA: <fato completo, fiel ao que ele disse>\n"
    "Exemplo: MEMORIA: O nome do usuário é Samuel. Não converta nem interprete horários: copie como ele falou."
)


def truncar(texto: str) -> str:
    return texto if len(texto) <= LIMITE else texto[:LIMITE] + "…"


def _agora(agora: datetime) -> str:
    return f"Agora é {DIAS[agora.weekday()]}, {agora:%d/%m/%Y %H:%M}."


def _pedido(instrucao: str, texto: str) -> list[dict]:
    return [{"role": "user", "content": f"{instrucao}\n\n{truncar(texto)}"}]


def mensagens_chat(historico: list[dict], memorias: list[str], agora: datetime) -> list[dict]:
    linhas = []
    for m in reversed(memorias):  # as mais novas primeiro, até o limite
        if sum(len(l) for l in linhas) + len(m) > LIMITE_MEMORIAS:
            break
        linhas.insert(0, f"- {m}")
    lembrancas = "\n".join(linhas) or "- (nada ainda)"
    cabeca = f"{PERSONALIDADE}\n\n{_agora(agora)}\nO que você lembra do usuário:\n{lembrancas}\n\n---\n\n"
    recentes, total = [], len(cabeca)
    for m in reversed(historico[-12:]):  # da mais nova pra trás, enquanto couber
        tamanho = len(truncar(m["content"]))
        if recentes and total + tamanho > ORCAMENTO:
            break
        recentes.insert(0, m)
        total += tamanho
    while recentes and recentes[0]["role"] != "user":  # Gemma exige começar em user
        recentes = recentes[1:]
    if not recentes:
        return []
    primeira = {"role": "user", "content": cabeca + truncar(recentes[0]["content"])}
    return [primeira] + [{"role": m["role"], "content": truncar(m["content"])} for m in recentes[1:]]


def _calendario(agora: datetime) -> str:
    # a Gemma erra conta de dia da semana; damos a tabela pronta
    dias = [agora + timedelta(days=i) for i in range(8)]
    return "Próximos dias: " + ", ".join(f"{DIAS[d.weekday()]} {d:%d/%m}" for d in dias) + "."


def mensagens_extrair(texto: str, agora: datetime) -> list[dict]:
    instrucao = (
        f"{_agora(agora)} {_calendario(agora)}\n"
        "Transforme o texto abaixo num lembrete. Responda SÓ com JSON, sem explicação:\n"
        '{"texto": "o que lembrar, curto", "quando": "AAAA-MM-DDTHH:MM" ou null se não tiver data/hora, '
        '"repete": null ou {"tipo": "diario"} ou {"tipo": "semanal", "dias": ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]} '
        'ou {"tipo": "mensal", "dia": 1-31}}\n'
        "Em \"dias\" ponha só os dias citados, pelo nome. Se só disser o dia sem hora, use 09:00. "
        "\"daqui X minutos\" conta a partir de agora. Se o texto não disser quando, \"quando\" é null: não invente data. "
        "Se o texto não disser que repete (todo, toda, cada, sempre), \"repete\" é null."
    )
    return _pedido(instrucao, texto)


def mensagens_melhorar(texto: str) -> list[dict]:
    return _pedido(
        "Melhore a mensagem abaixo: corrija erros e deixe mais clara e natural, mantendo o sentido, o tom e a língua. "
        "Responda SÓ com a mensagem melhorada, sem comentários.", texto)


def parece_portugues(texto: str) -> bool:
    palavras = re.findall(r"[a-zà-ú]+", texto.lower())
    pontos = sum(p in PALAVRAS_PT for p in palavras) + 2 * bool(re.search("[ãõç]", texto.lower()))
    return pontos >= max(1, len(palavras) * 0.1)


def mensagens_traduzir(texto: str) -> list[dict]:
    # a Gemma não segue bem "se for X traduza para Y": o código decide a língua
    destino = "inglês" if parece_portugues(texto) else "português do Brasil"
    return _pedido(f"Traduza o texto abaixo para {destino}. Responda SÓ com a tradução, sem comentários.", texto)


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


def _dia(d) -> int | None:
    if isinstance(d, int):
        return d if 0 <= d <= 6 else None
    if isinstance(d, str):
        sigla = unicodedata.normalize("NFKD", d).encode("ascii", "ignore").decode().lower().strip()[:3]
        return SIGLAS.index(sigla) if sigla in SIGLAS else None
    return None


def _regra_valida(r) -> dict | None:
    if not isinstance(r, dict):
        return None
    if r.get("tipo") == "diario":
        return {"tipo": "diario"}
    if r.get("tipo") == "semanal" and isinstance(r.get("dias"), list) and r["dias"]:
        dias = [_dia(d) for d in r["dias"]]
        if None not in dias:
            return {"tipo": "semanal", "dias": sorted(set(dias))}
    if r.get("tipo") == "mensal" and isinstance(r.get("dia"), int) and 1 <= r["dia"] <= 31:
        return {"tipo": "mensal", "dia": r["dia"]}
    return None


def ler_extracao(resposta: str) -> tuple[str, datetime | None, dict | None] | None:
    obj = _primeiro_objeto(resposta)
    if not obj or not isinstance(obj.get("texto"), str) or not obj["texto"].strip():
        return None
    try:
        quando = datetime.fromisoformat(obj.get("quando"))
        if quando.tzinfo:  # "...Z" ou "-03:00": vira hora local sem fuso, como o resto do app
            quando = quando.astimezone().replace(tzinfo=None)
    except (TypeError, ValueError):
        quando = None
    texto = re.sub(r"^\s*me\s+lembr[ae]\s+(de\s+)?", "", obj["texto"], flags=re.IGNORECASE).strip()
    return texto or obj["texto"].strip(), quando, _regra_valida(obj.get("repete"))


def conferir_extracao(original: str, quando: datetime | None, regra: dict | None) -> tuple[datetime | None, dict | None]:
    """Descarta data ou repetição que a Gemma inventou quando o texto não fala disso."""
    if not TEMPO.search(original):
        return None, None
    return quando, regra if REPETICAO.search(original) else None


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
