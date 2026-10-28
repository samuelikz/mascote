import json
import os
import sys
from pathlib import Path


PADROES = {
    "canto": "inf_dir", "ultima_comida": None, "almoco": "12:00", "bom_dia": None,
    "iniciativa": True, "voz": False, "area_transferencia": False, "cor": "verde", "acessorio": "nenhum",
}


def identidade() -> str:
    """Nome da pasta onde o .exe foi instalado ("Mascote", ou "MascoteTeste" no instalador de teste).
    Registro, dados e modelo seguem essa identidade, então duas instalações não se misturam."""
    if getattr(sys, "frozen", False):
        pasta = Path(sys.executable).parent.name
        if pasta.lower().startswith("mascote"):
            return pasta
    return "Mascote"


def pasta_dados() -> Path:
    pasta = Path(os.environ.get("MASCOTE_DADOS") or Path(os.environ["LOCALAPPDATA"]) / identidade() / "dados")
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def ler_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def gravar_json(caminho: Path, dados) -> None:
    # grava num temporário e troca de uma vez: queda de energia no meio não estraga o arquivo
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporario, caminho)


def carregar() -> dict:
    lido = ler_json(pasta_dados() / "config.json", {})
    return {**PADROES, **(lido if isinstance(lido, dict) else {})}


def salvar(cfg: dict) -> None:
    gravar_json(pasta_dados() / "config.json", cfg)


# ---- preferências escolhidas no instalador (HKCU\Software\Mascote) ----
PREFERENCIAS_PADRAO = {"Nome": "Mascote", "IA": "embutida", "ModeloOllama": "gemma2:9b"}


def _chave_registro() -> str:
    return os.environ.get("MASCOTE_REGISTRO", rf"Software\{identidade()}")


def preferencias() -> dict:
    import winreg

    prefs = dict(PREFERENCIAS_PADRAO)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _chave_registro()) as chave:
            for nome in prefs:
                try:
                    valor = str(winreg.QueryValueEx(chave, nome)[0]).strip()
                except OSError:
                    continue
                if valor:
                    prefs[nome] = valor
    except OSError:
        pass
    if prefs["IA"] not in ("embutida", "ollama"):
        prefs["IA"] = "embutida"
    return prefs


def salvar_preferencia(nome: str, valor: str) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _chave_registro()) as chave:
        winreg.SetValueEx(chave, nome, 0, winreg.REG_SZ, valor)
