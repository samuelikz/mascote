"""Integração com o Claude Code: hooks do Claude chamam `Mascote.exe --claude <evento>`, que grava o evento
num arquivo da pasta de dados; o pet aberto vigia esse arquivo e reage (pensando, terminou, precisa de você)."""
import shutil
import sys
from pathlib import Path

from .config import gravar_json, ler_json, pasta_dados

EVENTOS = {"UserPromptSubmit": "pensando", "Stop": "pronto", "Notification": "chamando"}
MARCA = "--claude"
CONFIG_CLAUDE = Path.home() / ".claude" / "settings.json"


def arquivo_evento() -> Path:
    return pasta_dados() / "claude.txt"


def comando(evento: str) -> str:
    if getattr(sys, "frozen", False):
        base = f'"{Path(sys.executable).as_posix()}"'
    else:
        # rodando do código: caminho absoluto, porque o hook roda na pasta do projeto que o Claude abriu
        base = f'"{Path(sys.executable).as_posix()}" "{(Path(__file__).parents[1] / "run_mascote.py").as_posix()}"'
    return f"{base} {MARCA} {evento}"


def _nosso(grupo) -> bool:
    return isinstance(grupo, dict) and any(MARCA in str(h.get("command", "")) and "ascote" in str(h.get("command", ""))
                                           for h in grupo.get("hooks", []) if isinstance(h, dict))


def remover_ganchos(dados: dict) -> dict:
    ganchos = dados.get("hooks")
    if isinstance(ganchos, dict):
        for nome in list(ganchos):
            if isinstance(ganchos[nome], list):
                ganchos[nome] = [g for g in ganchos[nome] if not _nosso(g)]
                if not ganchos[nome]:
                    del ganchos[nome]
        if not ganchos:
            del dados["hooks"]
    return dados


def instalar_ganchos(dados: dict) -> dict:
    """Acrescenta (ou troca) só os nossos hooks; os do usuário ficam como estão."""
    remover_ganchos(dados)
    ganchos = dados.setdefault("hooks", {})
    for nome, evento in EVENTOS.items():
        ganchos.setdefault(nome, []).append({"hooks": [{"type": "command", "command": comando(evento)}]})
    return dados


def ligado() -> bool:
    dados = ler_json(CONFIG_CLAUDE, {})
    return isinstance(dados, dict) and any(_nosso(g) for gs in (dados.get("hooks") or {}).values() for g in gs)


def ligar(sim: bool) -> None:
    dados = ler_json(CONFIG_CLAUDE, {})
    if not isinstance(dados, dict):
        raise ValueError(f"{CONFIG_CLAUDE} não é um JSON válido; não mexi nele")
    copia = CONFIG_CLAUDE.with_name("settings.json.antes-do-mascote")
    if CONFIG_CLAUDE.exists() and not copia.exists():
        shutil.copy2(CONFIG_CLAUDE, copia)
    CONFIG_CLAUDE.parent.mkdir(parents=True, exist_ok=True)
    gravar_json(CONFIG_CLAUDE, instalar_ganchos(dados) if sim else remover_ganchos(dados))


def gravar_evento(evento: str) -> None:
    if evento in EVENTOS.values():
        arquivo_evento().write_text(evento, encoding="utf-8")
