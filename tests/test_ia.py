import sys
import time
from pathlib import Path

import pytest

from mascote.ia import ErroIA, ServidorIA


def test_exe_inexistente_falha_rapido(tmp_path):  # Review Focus 4
    s = ServidorIA(tmp_path / "nao.exe", tmp_path / "nao.gguf")
    with pytest.raises(ErroIA):
        s.perguntar([{"role": "user", "content": "oi"}])
    assert not s.ligado


def test_processo_que_morre_vira_erro(tmp_path):  # Review Focus 4
    (tmp_path / "x.gguf").write_bytes(b"")
    s = ServidorIA(Path(sys.executable), tmp_path / "x.gguf", timeout_s=10)  # python sai com erro nos args
    t = time.time()
    with pytest.raises(ErroIA):
        s.garantir_ligado()
    assert time.time() - t < 10
    assert not s.ligado


@pytest.mark.skipif(not ServidorIA.padrao().disponivel(), reason="IA embutida não baixada")
def test_gemma_de_verdade_responde_e_desliga():
    s = ServidorIA.padrao(ocioso_s=0)
    t = time.time()
    resposta = s.perguntar([{"role": "user", "content": "Responda só: oi"}], max_tokens=16)
    print(f"\nprimeira resposta em {time.time() - t:.1f}s: {resposta!r}")
    assert resposta.strip()
    s.desligar_se_ocioso(time.time() + 1)
    assert not s.ligado


@pytest.mark.skipif(not ServidorIA.padrao().disponivel(), reason="IA embutida não baixada")
def test_servidor_recusa_pedido_sem_senha():
    import urllib.error
    import urllib.request

    s = ServidorIA.padrao()
    try:
        s.garantir_ligado()
        pedido = urllib.request.Request(s._url("/v1/models"))
        with pytest.raises(urllib.error.HTTPError) as erro:
            urllib.request.urlopen(pedido, timeout=5)
        assert erro.value.code == 401
    finally:
        s.desligar()


@pytest.mark.skipif(not ServidorIA.padrao().disponivel(), reason="IA embutida não baixada")
def test_servidor_morre_junto_quando_o_pet_e_morto(tmp_path):
    import subprocess

    codigo = (
        "import sys; sys.path.insert(0, r'%s'); from mascote.ia import ServidorIA; "
        "s = ServidorIA.padrao(); s.garantir_ligado(); print(s.proc.pid, flush=True); import time; time.sleep(60)"
    ) % Path(__file__).resolve().parent.parent
    pai = subprocess.Popen([sys.executable, "-c", codigo], stdout=subprocess.PIPE, text=True)
    filho = int(pai.stdout.readline())
    pai.kill()  # como o Gerenciador de Tarefas faria
    pai.wait()
    time.sleep(2)
    vivos = subprocess.run(["tasklist", "/FI", f"PID eq {filho}", "/NH"], capture_output=True, text=True).stdout
    if str(filho) in vivos:
        subprocess.run(["taskkill", "/F", "/PID", str(filho)])
    assert str(filho) not in vivos


def _ollama_no_ar():
    import urllib.request

    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2)
        return True
    except OSError:
        return False


def test_ollama_fechado_vira_erro_rapido():
    from mascote.ia import ClienteOllama

    t = time.time()
    with pytest.raises(ErroIA, match="Ollama"):
        ClienteOllama("gemma2:9b", url="http://127.0.0.1:9").perguntar([{"role": "user", "content": "oi"}])
    assert time.time() - t < 5


def test_criar_ia_conforme_preferencias():
    from mascote.baixar import caminho_modelo
    from mascote.ia import ClienteOllama, criar_ia

    ia = criar_ia({"IA": "ollama", "ModeloOllama": "dolphin-mistral:latest"})
    assert isinstance(ia, ClienteOllama) and ia.modelo == "dolphin-mistral:latest"
    embutida = criar_ia({"IA": "embutida", "ModeloOllama": "x"})
    assert isinstance(embutida, ServidorIA) and embutida.modelo == caminho_modelo("gemma2")
    leve = criar_ia({"IA": "embutida", "ModeloOllama": "x", "Cerebro": "qwen35"})
    assert leve.modelo.name == "qwen3.5-4b.gguf"


def test_sem_pensamento_tira_o_raciocinio_do_qwen():
    from mascote.ia import sem_pensamento

    assert sem_pensamento("<think>\nhmm, o usuário quer...\n</think>\n\noi! 😄") == "oi! 😄"
    assert sem_pensamento("<think>ainda pensando") == ""  # resposta chegando aos poucos
    assert sem_pensamento("oi sem pensar") == "oi sem pensar"


@pytest.mark.skipif(not _ollama_no_ar(), reason="Ollama não está rodando")
def test_ollama_de_verdade_lista_modelos_e_responde():
    from mascote.ia import ClienteOllama

    cliente = ClienteOllama("gemma2:9b", manter="0")  # descarrega logo, pra não brigar por VRAM com o llama-server
    assert "gemma2:9b" in cliente.modelos()
    assert cliente.perguntar([{"role": "user", "content": "Responda só: oi"}], max_tokens=16).strip()


def test_juntar_fluxo_do_llama_e_do_ollama():
    from mascote.ia import juntar_fluxo

    vistos = []
    sse = [b'data: {"choices":[{"delta":{"content":"oi"}}]}\n', b"\n", b'data: {"choices":[{"delta":{"content":"\xc3\xaa!"}}]}\n',
           b'data: {"choices":[{"delta":{}}]}\n', b"data: [DONE]\n"]
    assert juntar_fluxo(sse, lambda o: o["choices"][0]["delta"].get("content"), vistos.append) == "oiê!"
    assert vistos == ["oi", "oiê!"]
    ndjson = [b'{"message":{"content":"tu"}}\n', b'{"message":{"content":"do"},"done":true}\n']
    assert juntar_fluxo(ndjson, lambda o: o["message"]["content"], lambda t: None) == "tudo"
