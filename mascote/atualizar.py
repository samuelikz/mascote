"""Verifica e aplica atualizações a partir das releases "vX.Y.Z" do GitHub do projeto.

A release "ia-v1" (modelo) é ignorada. Cada release de versão traz MascoteSetup.exe e Mascote-teste-setup.exe;
o pet baixa o da sua identidade, confere tamanho (e SHA-256, quando o GitHub informa) e roda em modo silencioso.
"""
import hashlib
import json
import os
import re
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .versao import VERSAO

API = "https://api.github.com/repos/samuelikz/mascote/releases?per_page=20"
BLOCO = 1024 * 1024


@dataclass
class Atualizacao:
    versao: str
    url: str
    tamanho: int
    sha256: str
    notas: str


def _tupla(v: str) -> tuple[int, ...] | None:
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", v.strip())
    return tuple(map(int, m.groups())) if m else None


def mais_nova(candidata: str, atual: str = VERSAO) -> bool:
    c, a = _tupla(candidata), _tupla(atual)
    return bool(c and a and c > a)


def nome_instalador() -> str:
    from .config import identidade

    return "Mascote-teste-setup.exe" if identidade().lower() == "mascoteteste" else "MascoteSetup.exe"


def escolher(releases: list[dict], atual: str = VERSAO, arquivo: str = "MascoteSetup.exe") -> Atualizacao | None:
    """A release de versão mais nova que `atual` que tenha o instalador; None se já está em dia."""
    melhor = None
    for r in releases:
        tag = r.get("tag_name", "")
        if r.get("draft") or r.get("prerelease") or not _tupla(tag) or not mais_nova(tag, atual):
            continue
        asset = next((a for a in r.get("assets", []) if a.get("name") == arquivo), None)
        if not asset:
            continue
        if melhor is None or _tupla(tag) > _tupla(melhor.versao):
            digest = asset.get("digest") or ""
            melhor = Atualizacao(tag.lstrip("v"), asset["browser_download_url"], int(asset.get("size", 0)),
                                 digest.removeprefix("sha256:") if digest.startswith("sha256:") else "",
                                 (r.get("body") or "").strip())
    return melhor


def verificar(timeout: float = 15) -> Atualizacao | None:
    pedido = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json", "User-Agent": f"Mascote/{VERSAO}"})
    with urllib.request.urlopen(pedido, timeout=timeout) as r:
        return escolher(json.load(r), VERSAO, nome_instalador())


def baixar(atu: Atualizacao, progresso: Callable[[int, int], None], cancelado: Callable[[], bool] = lambda: False,
           pasta: Path | None = None) -> Path:
    destino = (pasta or Path(tempfile.gettempdir())) / f"Mascote-{atu.versao}-setup.exe"
    h, feito = hashlib.sha256(), 0
    pedido = urllib.request.Request(atu.url, headers={"User-Agent": f"Mascote/{VERSAO}"})
    with urllib.request.urlopen(pedido, timeout=30) as r, open(destino, "wb") as f:
        total = atu.tamanho or int(r.headers.get("Content-Length") or 0)
        while bloco := r.read(BLOCO):
            if cancelado():
                raise InterruptedError("cancelado")
            f.write(bloco)
            h.update(bloco)
            feito += len(bloco)
            progresso(feito, total)
    if (atu.tamanho and feito != atu.tamanho) or (atu.sha256 and h.hexdigest() != atu.sha256):
        destino.unlink(missing_ok=True)
        raise ValueError("o instalador baixado veio corrompido")
    return destino


def instalar(setup: Path) -> None:
    """Abre o instalador (pede administrador) em modo silencioso; ele fecha o pet e o reabre no fim."""
    os.startfile(str(setup), "runas", "/SILENT /SUPPRESSMSGBOXES /NORESTART")
