from .config import gravar_json, ler_json, pasta_dados


def _arquivo():
    return pasta_dados() / "memorias.json"


def listar() -> list[dict]:
    dados = ler_json(_arquivo(), [])
    return dados if isinstance(dados, list) else []


def adicionar(fato: str) -> dict | None:
    fato = fato.strip()
    itens = listar()
    existente = next((m for m in itens if m["fato"].lower() == fato.lower()), None)
    if not fato or existente:
        return existente
    novo = {"id": max((m["id"] for m in itens), default=0) + 1, "fato": fato}
    gravar_json(_arquivo(), itens + [novo])
    return novo


def apagar(id: int) -> None:
    gravar_json(_arquivo(), [m for m in listar() if m["id"] != id])
