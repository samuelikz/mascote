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


@pytest.mark.skipif(not ServidorIA.padrao().disponivel(), reason="recursos/ ausente")
def test_gemma_de_verdade_responde_e_desliga():
    s = ServidorIA.padrao(ocioso_s=0)
    t = time.time()
    resposta = s.perguntar([{"role": "user", "content": "Responda só: oi"}], max_tokens=16)
    print(f"\nprimeira resposta em {time.time() - t:.1f}s: {resposta!r}")
    assert resposta.strip()
    s.desligar_se_ocioso(time.time() + 1)
    assert not s.ligado


@pytest.mark.skipif(not ServidorIA.padrao().disponivel(), reason="recursos/ ausente")
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
