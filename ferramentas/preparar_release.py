"""Monta dist/release/ com os arquivos da release "ia-v1" que o instalador baixa:
partes da Gemma (< 2 GB cada, limite do GitHub), zip do llama.cpp e os termos de uso da Gemma.

Uso: python ferramentas/preparar_release.py
Depois: gh release create ia-v1 dist/release/* -R samuelikz/mascote --title "IA do Mascote" --notes-file dist/release/NOTAS.md
"""
import hashlib
import sys
from pathlib import Path

from mascote import baixar

SAIDA = Path("dist/release")
TERMOS_OLLAMA = Path.home() / ".ollama/models/blobs/sha256-097a36493f718248845233af1d3fefe7a303f864fae13bc31a3a9704229378ca"


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while bloco := f.read(baixar.BLOCO):
            h.update(bloco)
    return h.hexdigest()


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    print("llama.cpp…")
    zip_ = SAIDA / baixar.LLAMA_ZIP
    baixar.baixar_arquivo(zip_, baixar.LLAMA_FONTES[1:], baixar.LLAMA_SHA256, baixar.LLAMA_TAMANHO, lambda *a: None)
    zip_.with_name(zip_.name + ".ok").unlink(missing_ok=True)

    modelo = baixar.caminho_modelo()
    if not baixar.pronto(modelo):
        print("modelo ainda não está na máquina; obtendo (copia do Ollama ou baixa)…")
        baixar.baixar_arquivo(modelo, baixar.MODELO_FONTES[1:], baixar.MODELO_SHA256, baixar.MODELO_TAMANHO,
                              lambda *a: None, copiar_de=baixar.BLOB_OLLAMA)
    with open(modelo, "rb") as origem:
        for url, tamanho in baixar.MODELO_FONTES[0]:
            parte = SAIDA / url.rsplit("/", 1)[1]
            print(f"{parte.name} ({tamanho:,} bytes)…")
            with open(parte, "wb") as destino:
                restante = tamanho
                while restante:
                    bloco = origem.read(min(baixar.BLOCO, restante))
                    destino.write(bloco)
                    restante -= len(bloco)
        assert origem.read(1) == b"", "o modelo é maior que a soma das partes"

    if not TERMOS_OLLAMA.is_file():
        sys.exit("faltam os termos da Gemma: baixe com `ollama pull gemma2:9b` ou copie de ai.google.dev/gemma/terms")
    (SAIDA / "GEMMA_TERMS.txt").write_bytes(TERMOS_OLLAMA.read_bytes())

    arquivos = sorted(p for p in SAIDA.iterdir() if p.name not in ("SHA256SUMS.txt", "NOTAS.md"))
    (SAIDA / "SHA256SUMS.txt").write_text("".join(f"{sha256(p)}  {p.name}\n" for p in arquivos), encoding="utf-8")
    (SAIDA / "NOTAS.md").write_text(
        "Arquivos que o instalador do Mascote baixa quando a opção **IA embutida** é escolhida.\n\n"
        "- `gemma2-9b.gguf.001`…`.003`: Gemma 2 9B (Q4_0) em partes (o GitHub limita 2 GB por arquivo). "
        f"Juntas formam um arquivo com SHA-256 `{baixar.MODELO_SHA256}`.\n"
        f"- `{baixar.LLAMA_ZIP}`: llama.cpp b11941 (build Vulkan), sem modificações.\n\n"
        "Gemma is provided under and subject to the Gemma Terms of Use found at ai.google.dev/gemma/terms "
        "(cópia em `GEMMA_TERMS.txt`).\n", encoding="utf-8")
    print("\n".join(f"  {p.name}  {p.stat().st_size:,}" for p in sorted(SAIDA.iterdir())))


if __name__ == "__main__":
    main()
