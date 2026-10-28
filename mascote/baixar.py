"""Obtém o modelo da IA embutida: copia do Ollama se já existir, senão baixa (retomável), sempre conferindo o SHA-256."""
import hashlib
import os
import urllib.request
from pathlib import Path
from typing import Callable

# Gemma 2 9B (Q4_0), o mesmo arquivo testado com o Mascote, servido pelo registro público do Ollama.
SHA256 = "ff1d1fc78170d787ee1201778e2dd65ea211654ca5fb7d69b5a2e7b123a50373"
TAMANHO = 5_443_143_296
URL = f"https://registry.ollama.ai/v2/library/gemma2/blobs/sha256:{SHA256}"
BLOB_OLLAMA = Path.home() / ".ollama" / "models" / "blobs" / f"sha256-{SHA256}"
BLOCO = 4 * 1024 * 1024


class ErroDownload(Exception):
    pass


def pasta_modelo() -> Path:
    from .config import identidade

    return Path(os.environ.get("MASCOTE_MODELO_DIR") or Path(os.environ["LOCALAPPDATA"]) / identidade() / "modelo")


def caminho_modelo() -> Path:
    return pasta_modelo() / "gemma2-9b.gguf"


def obter_modelo(
    destino: Path,
    progresso: Callable[[int, int], None],
    url: str = URL,
    sha256: str = SHA256,
    tamanho: int = TAMANHO,
    blob_ollama: Path = BLOB_OLLAMA,
    cancelado: Callable[[], bool] = lambda: False,
) -> None:
    destino = Path(destino)
    pronto = destino.with_name(destino.name + ".ok")  # marca: já conferido, não precisa reler 5 GB
    if destino.is_file() and pronto.is_file() and destino.stat().st_size == tamanho:
        progresso(tamanho, tamanho)
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".part")
    resumo = hashlib.sha256()

    def gravar(origem, saida, feito: int) -> int:
        while bloco := origem.read(BLOCO):
            if cancelado():
                raise ErroDownload("cancelado")
            saida.write(bloco)
            resumo.update(bloco)
            feito += len(bloco)
            progresso(feito, tamanho)
        return feito

    if blob_ollama.is_file() and blob_ollama.stat().st_size == tamanho:
        with open(blob_ollama, "rb") as origem, open(parcial, "wb") as saida:
            feito = gravar(origem, saida, 0)
    else:
        feito = parcial.stat().st_size if parcial.is_file() else 0
        if feito > tamanho:
            parcial.unlink()
            feito = 0
        if feito:  # retomando: o hash precisa incluir o que já veio
            with open(parcial, "rb") as ja:
                while bloco := ja.read(BLOCO):
                    resumo.update(bloco)
        pedido = urllib.request.Request(url, headers={"Range": f"bytes={feito}-"} if feito else {})
        try:
            with urllib.request.urlopen(pedido, timeout=60) as r, open(parcial, "ab" if feito else "wb") as saida:
                if feito and r.status != 206:  # servidor ignorou o Range: recomeça do zero
                    saida.truncate(0)
                    resumo, feito = hashlib.sha256(), 0
                feito = gravar(r, saida, feito)
        except OSError as e:
            raise ErroDownload(f"falha no download: {e}") from e

    if feito != tamanho or resumo.hexdigest() != sha256:
        parcial.unlink(missing_ok=True)
        raise ErroDownload("o arquivo baixado não confere (SHA-256)")
    os.replace(parcial, destino)
    pronto.write_text(sha256, encoding="utf-8")
