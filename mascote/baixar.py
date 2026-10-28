"""Obtém a IA embutida (llama.cpp + um modelo: Gemma 2 9B ou Qwen3.5 4B) na pasta do usuário, conferindo SHA-256.

Fonte principal: a release "ia-v1" do repositório do projeto (o GitHub limita 2 GB por arquivo, então o
modelo vai em partes). Se ela falhar, usa as fontes originais. Se a Gemma já estiver no Ollama, copia de lá.
"""
import hashlib
import os
import zipfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

REPO = "https://github.com/samuelikz/mascote/releases/download/ia-v1"
BLOCO = 4 * 1024 * 1024
PARTE = 1_900_000_000

Progresso = Callable[[int, int], None]


def _partes(nome: str, total: int) -> list[tuple[str, int]]:
    tamanhos = [min(PARTE, total - i) for i in range(0, total, PARTE)]
    return [(f"{REPO}/{nome}.{n:03d}", t) for n, t in enumerate(tamanhos, 1)]


@dataclass(frozen=True)
class Modelo:
    nome: str  # como aparece pro usuário
    arquivo: str
    sha256: str
    tamanho: int
    fontes: list
    copiar_de: Path | None = None  # mesmo arquivo já baixado pelo Ollama
    contexto: int = 8192  # tokens; a Gemma 9B com 8192 não cabe numa placa de 8 GB (memória de vídeo esgota)

    @property
    def gb(self) -> str:
        return f"{self.tamanho / 1e9:.1f} GB".replace(".", ",")


_GEMMA_SHA = "ff1d1fc78170d787ee1201778e2dd65ea211654ca5fb7d69b5a2e7b123a50373"
_QWEN_SHA = "13c16f426047e2de38cd075bdade4a7bcbc8c774384876f677740cda65f8a983"
MODELOS = {
    # Gemma 2 9B (Q4_0): o mesmo arquivo testado com o Mascote
    "gemma2": Modelo("Gemma 2 9B", "gemma2-9b.gguf", _GEMMA_SHA, 5_443_143_296, [
        _partes("gemma2-9b.gguf", 5_443_143_296),
        [(f"https://registry.ollama.ai/v2/library/gemma2/blobs/sha256:{_GEMMA_SHA}", 5_443_143_296)],
    ], Path.home() / ".ollama" / "models" / "blobs" / f"sha256-{_GEMMA_SHA}", contexto=4096),
    # Qwen3.5 4B (Q4_K_M, quantizado pelo bartowski): mais leve, roda em placas com menos memória
    "qwen35": Modelo("Qwen3.5 4B", "qwen3.5-4b.gguf", _QWEN_SHA, 3_013_027_808, [
        _partes("qwen3.5-4b.gguf", 3_013_027_808),
        [("https://huggingface.co/bartowski/Qwen_Qwen3.5-4B-GGUF/resolve/main/Qwen_Qwen3.5-4B-Q4_K_M.gguf", 3_013_027_808)],
    ]),
}
PADRAO = "gemma2"


def modelo(chave: str | None = None) -> Modelo:
    """O modelo escolhido (no instalador ou no menu), ou o de `chave`."""
    if chave is None:
        from .config import preferencias

        chave = preferencias()["Cerebro"]
    return MODELOS.get(chave, MODELOS[PADRAO])

# llama.cpp b11941, build Vulkan (funciona em placas AMD como a RX 580)
LLAMA_ZIP = "llama-b11941-bin-win-vulkan-x64.zip"
LLAMA_SHA256 = "3383efca87453d1d1e564b91d95db16d5b511ec72fad4983fd99ea8774649fd6"
LLAMA_TAMANHO = 37_230_602
LLAMA_FONTES = [
    [(f"{REPO}/{LLAMA_ZIP}", LLAMA_TAMANHO)],
    [(f"https://github.com/ggml-org/llama.cpp/releases/download/b11941/{LLAMA_ZIP}", LLAMA_TAMANHO)],
]


class ErroDownload(Exception):
    pass


def pasta_ia() -> Path:
    from .config import identidade

    return Path(os.environ.get("MASCOTE_IA_DIR") or Path(os.environ["LOCALAPPDATA"]) / identidade())


def caminho_modelo(chave: str | None = None) -> Path:
    return pasta_ia() / "modelo" / modelo(chave).arquivo


def caminho_llama() -> Path:
    return pasta_ia() / "llama" / "llama-server.exe"


def _marca(arquivo: Path) -> Path:
    return arquivo.with_name(arquivo.name + ".ok")  # já conferido: não precisa reler GBs


def pronto(arquivo: Path) -> bool:
    return arquivo.is_file() and _marca(arquivo).is_file()


def ia_instalada(chave: str | None = None) -> bool:
    return pronto(caminho_modelo(chave)) and pronto(caminho_llama())


def baixar_arquivo(
    destino: Path,
    fontes: list[list[tuple[str, int]]],
    sha256: str,
    tamanho: int,
    progresso: Progresso,
    cancelado: Callable[[], bool] = lambda: False,
    copiar_de: Path | None = None,
) -> None:
    """Grava `destino` a partir da primeira fonte que der certo. Cada fonte é uma lista de partes (url, tamanho)
    que, juntas, formam o arquivo. O download continua de onde parou (.part) e o SHA-256 confere o resultado."""
    destino = Path(destino)
    if pronto(destino) and destino.stat().st_size == tamanho:
        progresso(tamanho, tamanho)
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".part")

    def copiar(origem, saida, feito: int) -> int:
        while bloco := origem.read(BLOCO):
            if cancelado():
                raise ErroDownload("cancelado")
            saida.write(bloco)
            feito += len(bloco)
            progresso(feito, tamanho)
        return feito

    if copiar_de and copiar_de.is_file() and copiar_de.stat().st_size == tamanho:
        with open(copiar_de, "rb") as origem, open(parcial, "wb") as saida:
            copiar(origem, saida, 0)
    else:
        erros = []
        for fonte in fontes:
            try:
                _baixar_fonte(parcial, fonte, tamanho, copiar)
                break
            except ErroDownload as e:
                if str(e) == "cancelado":
                    raise
                erros.append(str(e))
        else:
            raise ErroDownload("nenhuma fonte funcionou: " + " | ".join(erros))

    resumo = hashlib.sha256()
    with open(parcial, "rb") as f:
        while bloco := f.read(BLOCO):
            resumo.update(bloco)
    if parcial.stat().st_size != tamanho or resumo.hexdigest() != sha256:
        parcial.unlink(missing_ok=True)
        raise ErroDownload("o arquivo baixado não confere (SHA-256)")
    os.replace(parcial, destino)
    _marca(destino).write_text(sha256, encoding="utf-8")


def _baixar_fonte(parcial: Path, partes: list[tuple[str, int]], tamanho: int, copiar) -> None:
    feito = parcial.stat().st_size if parcial.is_file() else 0
    if feito > tamanho:
        parcial.unlink()
        feito = 0
    inicio = 0
    for url, tam in partes:
        fim = inicio + tam
        if feito < fim:
            desloc = feito - inicio  # quanto desta parte já veio
            pedido = urllib.request.Request(url, headers={"Range": f"bytes={desloc}-"} if desloc else {})
            try:
                with urllib.request.urlopen(pedido, timeout=60) as r, open(parcial, "r+b" if feito else "wb") as saida:
                    if desloc and r.status != 206:  # servidor ignorou o Range: refaz esta parte inteira
                        desloc = 0
                    saida.seek(inicio + desloc)
                    saida.truncate()
                    feito = copiar(r, saida, inicio + desloc)
            except (urllib.error.URLError, OSError) as e:
                raise ErroDownload(f"{url}: {e}") from e
            if feito != fim:
                raise ErroDownload(f"{url}: veio incompleto")
        inicio = fim


def instalar_llama(zip_: Path, pasta: Path) -> None:
    """Extrai só o servidor e as DLLs (pelo nome do arquivo, sem caminhos: nada sai da pasta)."""
    pasta.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_) as z:
        for item in z.infolist():
            nome = PurePosixPath(item.filename.replace("\\", "/")).name
            if nome == "llama-server.exe" or nome.lower().endswith(".dll"):
                (pasta / nome).write_bytes(z.read(item))


def obter_ia(progresso: Progresso, cancelado: Callable[[], bool] = lambda: False, chave: str | None = None) -> None:
    """Baixa o que faltar (llama.cpp e modelo), com um progresso só somando os dois."""
    m = modelo(chave)
    falta_llama = not pronto(caminho_llama())
    total = (LLAMA_TAMANHO if falta_llama else 0) + m.tamanho
    if falta_llama:
        zip_ = pasta_ia() / "llama" / LLAMA_ZIP
        baixar_arquivo(zip_, LLAMA_FONTES, LLAMA_SHA256, LLAMA_TAMANHO, lambda f, t: progresso(f, total), cancelado)
        instalar_llama(zip_, caminho_llama().parent)
        zip_.unlink()
        _marca(zip_).unlink(missing_ok=True)
        _marca(caminho_llama()).write_text(LLAMA_SHA256, encoding="utf-8")
    base = LLAMA_TAMANHO if falta_llama else 0
    baixar_arquivo(caminho_modelo(chave), m.fontes, m.sha256, m.tamanho,
                   lambda f, t: progresso(base + f, total), cancelado, copiar_de=m.copiar_de)
