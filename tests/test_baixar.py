import hashlib
import http.server
import threading

import pytest

from mascote.baixar import ErroDownload, obter_modelo

CONTEUDO = bytes(range(256)) * 4000  # ~1 MB
SHA = hashlib.sha256(CONTEUDO).hexdigest()


@pytest.fixture
def servidor():
    pedidos = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            inicio = int(self.headers.get("Range", "bytes=0-").split("=")[1].split("-")[0])
            pedidos.append(inicio)
            self.send_response(206 if inicio else 200)
            self.send_header("Content-Length", str(len(CONTEUDO) - inicio))
            self.end_headers()
            self.wfile.write(CONTEUDO[inicio:])

        def log_message(self, *a):
            pass

    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}/modelo", pedidos
    s.shutdown()


def baixar(destino, url, **kw):
    progresso = []
    obter_modelo(destino, lambda feito, total: progresso.append((feito, total)), url=url, sha256=SHA,
                 tamanho=len(CONTEUDO), **{"blob_ollama": destino.parent / "nao-existe", **kw})
    return progresso


def test_baixa_confere_e_mostra_progresso(tmp_path, servidor):
    url, _ = servidor
    progresso = baixar(tmp_path / "m.gguf", url)
    assert (tmp_path / "m.gguf").read_bytes() == CONTEUDO
    assert progresso[-1] == (len(CONTEUDO), len(CONTEUDO))
    assert not (tmp_path / "m.gguf.part").exists()


def test_continua_de_onde_parou(tmp_path, servidor):
    url, pedidos = servidor
    (tmp_path / "m.gguf.part").write_bytes(CONTEUDO[:300_000])
    baixar(tmp_path / "m.gguf", url)
    assert pedidos == [300_000] and (tmp_path / "m.gguf").read_bytes() == CONTEUDO


def test_hash_errado_apaga_e_falha(tmp_path, servidor):
    url, _ = servidor
    with pytest.raises(ErroDownload):
        obter_modelo(tmp_path / "m.gguf", lambda *a: None, url=url, sha256="0" * 64, tamanho=len(CONTEUDO),
                     blob_ollama=tmp_path / "nao-existe")
    assert not (tmp_path / "m.gguf").exists() and not (tmp_path / "m.gguf.part").exists()


def test_copia_do_ollama_sem_baixar(tmp_path, servidor):
    url, pedidos = servidor
    blob = tmp_path / "blob"
    blob.write_bytes(CONTEUDO)
    baixar(tmp_path / "m.gguf", url, blob_ollama=blob)
    assert pedidos == [] and (tmp_path / "m.gguf").read_bytes() == CONTEUDO


def test_ja_baixado_nao_faz_nada(tmp_path, servidor):
    url, pedidos = servidor
    baixar(tmp_path / "m.gguf", url)
    baixar(tmp_path / "m.gguf", url)
    assert len(pedidos) == 1


def test_cancelar_para_e_guarda_o_parcial(tmp_path, servidor):
    url, _ = servidor
    with pytest.raises(ErroDownload):
        obter_modelo(tmp_path / "m.gguf", lambda *a: None, url=url, sha256=SHA, tamanho=len(CONTEUDO),
                     blob_ollama=tmp_path / "nao-existe", cancelado=lambda: True)
    assert not (tmp_path / "m.gguf").exists()
