"""Diário de convivência: o que aconteceu em cada dia e os pontos de amizade. Vive dentro do config.json."""
from datetime import date, timedelta

PONTOS = {"lembretes": 3, "focos": 5, "comidas": 2, "carinhos": 1, "conversas": 1}
NIVEIS = [  # (pontos mínimos, nome, como falar com o usuário)
    (0, "conhecidos", "Vocês ainda estão se conhecendo: seja fofo, mas um pouquinho tímido."),
    (20, "colegas", "Vocês já são colegas: seja simpático e brincalhão."),
    (60, "amigos", "Vocês são amigos: seja carinhoso e à vontade."),
    (150, "melhores amigos", "Vocês são melhores amigos: seja bem carinhoso, lembre de coisas que ele contou."),
    (300, "inseparáveis", "Vocês são inseparáveis: seja muito carinhoso e íntimo, pode usar apelidos fofos."),
    (600, "almas gêmeas", "Vocês são almas gêmeas: trate o usuário como a pessoa favorita do mundo."),
]
PREMIOS = {"cachecol": 2, "coroa": 3, "dourado": 4}  # item: nível que libera
GUARDAR_DIAS = 60


def registrar(cfg: dict, tipo: str, hoje: date) -> bool:
    """Conta `tipo` no dia de hoje e soma os pontos. True se subiu de nível."""
    antes = nivel(cfg)[0]
    dias = cfg.setdefault("diario", {})
    dia = dias.setdefault(hoje.isoformat(), {})
    dia[tipo] = dia.get(tipo, 0) + 1
    cfg["amizade"] = cfg.get("amizade", 0) + PONTOS[tipo]
    limite = (hoje - timedelta(days=GUARDAR_DIAS)).isoformat()
    for velho in [d for d in dias if d < limite]:
        del dias[velho]
    return nivel(cfg)[0] > antes


def nivel(cfg: dict) -> tuple[int, str, str, int | None]:
    """(índice, nome, tom, pontos que faltam pro próximo ou None no último)."""
    pontos = cfg.get("amizade", 0)
    i = max(n for n, (minimo, _, _) in enumerate(NIVEIS) if pontos >= minimo)
    falta = NIVEIS[i + 1][0] - pontos if i + 1 < len(NIVEIS) else None
    return i, NIVEIS[i][1], NIVEIS[i][2], falta


def liberado(cfg: dict, item: str) -> bool:
    return nivel(cfg)[0] >= PREMIOS.get(item, 0)


def semana(cfg: dict, fim: date) -> dict[str, int]:
    """Totais dos 7 dias que terminam em `fim` (inclusive)."""
    total = dict.fromkeys(PONTOS, 0)
    for i in range(7):
        for tipo, n in cfg.get("diario", {}).get((fim - timedelta(days=i)).isoformat(), {}).items():
            if tipo in total:
                total[tipo] += n
    return total


def descrever_semana(totais: dict[str, int]) -> str:
    partes = [f"✅ {totais['lembretes']} lembretes", f"🍅 {totais['focos']} focos", f"😋 {totais['comidas']} comidas",
              f"🥰 {totais['carinhos']} carinhos", f"💬 {totais['conversas']} conversas"]
    return " · ".join(p for p, n in zip(partes, totais.values()) if n) or "nada ainda… bora fazer coisas juntos? 🥺"
