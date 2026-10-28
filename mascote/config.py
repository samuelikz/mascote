import json
import os
import sys
from pathlib import Path

PASTA_APP = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
RECURSOS = PASTA_APP / "recursos"

PADROES = {"canto": "inf_dir", "ultima_comida": None}


def pasta_dados() -> Path:
    pasta = Path(os.environ.get("MASCOTE_DADOS") or Path(os.environ["LOCALAPPDATA"]) / "Mascote" / "dados")
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def ler_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def gravar_json(caminho: Path, dados) -> None:
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def carregar() -> dict:
    lido = ler_json(pasta_dados() / "config.json", {})
    return {**PADROES, **(lido if isinstance(lido, dict) else {})}


def salvar(cfg: dict) -> None:
    gravar_json(pasta_dados() / "config.json", cfg)
