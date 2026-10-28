import hashlib
import http.server
import io
import threading
import zipfile

import pytest

from mascote import baixar
from mascote.baixar import ErroDownload, baixar_arquivo, instalar_llama

CONTEUDO = bytes(range(256)) * 4000  # ~1 MB
SHA = hashlib.sha256(CONTEUDO).hexdigest()
CORTES = [0, 400_000, 800_000, len(CONTEUDO)]
ARQUIVOS = {
    "/p1": CONTEUDO[CORTES[0]:CORTES[1]],
    "/p2": CONTEUDO[CORTES[1]:CORTES[2]],
    "/p3": CONTEUDO[CORTES[2]:CORTES[3]],
    "/tudo": CONTEUDO,
}


@pytest.fixture
def servidor():
    pedidos = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            dados = ARQUIVOS.get(self.path)
            inicio = int(self.headers.get("Range", "bytes=0-").split("=")[1].split("-")[0])
            pedidos.append((self.path, inicio))
            if dados is None:
                self.send_error(404)
                return
            self.send_response(206 if inicio else 200)
            self.send_header("Content-Length", str(len(dados) - inicio))
            self.end_headers()
            self.wfile.write(dados[inicio:])

        def log_message(self, *a):
            pass

    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{s.server_port}"
    em_partes = [(base + p, CORTES[i + 1] - CORTES[i]) for i, p in enumerate(["/p1", "/p2", "/p3"])]
    yield base, em_partes, pedidos
    s.shutdown()


def baixar_teste(destino, fontes, **kw):
    progresso = []
    baixar_arquivo(destino, fontes, SHA, len(CONTEUDO), lambda f, t: progresso.append((f, t)), **kw)
    return progresso


def test_junta_as_partes_confere_e_mostra_progresso(tmp_path, servidor):
    _, partes, _ = servidor
    progresso = baixar_teste(tmp_path / "m.gguf", [partes])
    assert (tmp_path / "m.gguf").read_bytes() == CONTEUDO
    assert progresso[-1] == (len(CONTEUDO), len(CONTEUDO))
    assert not (tmp_path / "m.gguf.part").exists()


def test_continua_no_meio_da_segunda_parte(tmp_path, servidor):
    _, partes, pedidos = servidor
    (tmp_path / "m.gguf.part").write_bytes(CONTEUDO[:401_000])
    baixar_teste(tmp_path / "m.gguf", [partes])
    assert pedidos == [("/p2", 1_000), ("/p3", 0)]
    assert (tmp_path / "m.gguf").read_bytes() == CONTEUDO


def test_se_o_github_falha_usa_a_fonte_original(tmp_path, servidor):
    base, _, pedidos = servidor
    baixar_teste(tmp_path / "m.gguf", [[(base + "/nao-tem", len(CONTEUDO))], [(base + "/tudo", len(CONTEUDO))]])
    assert [p for p, _ in pedidos] == ["/nao-tem", "/tudo"]
    assert (tmp_path / "m.gguf").read_bytes() == CONTEUDO


def test_hash_errado_apaga_e_falha(tmp_path, servidor):
    _, partes, _ = servidor
    with pytest.raises(ErroDownload):
        baixar_arquivo(tmp_path / "m.gguf", [partes], "0" * 64, len(CONTEUDO), lambda *a: None)
    assert not (tmp_path / "m.gguf").exists() and not (tmp_path / "m.gguf.part").exists()


def test_copia_do_ollama_sem_baixar(tmp_path, servidor):
    _, partes, pedidos = servidor
    blob = tmp_path / "blob"
    blob.write_bytes(CONTEUDO)
    baixar_teste(tmp_path / "m.gguf", [partes], copiar_de=blob)
    assert pedidos == [] and (tmp_path / "m.gguf").read_bytes() == CONTEUDO


def test_ja_baixado_nao_faz_nada(tmp_path, servidor):
    _, partes, pedidos = servidor
    baixar_teste(tmp_path / "m.gguf", [partes])
    baixar_teste(tmp_path / "m.gguf", [partes])
    assert len(pedidos) == 3


def test_cancelar_para_sem_criar_o_arquivo(tmp_path, servidor):
    _, partes, _ = servidor
    with pytest.raises(ErroDownload):
        baixar_arquivo(tmp_path / "m.gguf", [partes], SHA, len(CONTEUDO), lambda *a: None, cancelado=lambda: True)
    assert not (tmp_path / "m.gguf").exists()


def test_llama_extrai_so_servidor_e_dlls_dentro_da_pasta(tmp_path):
    zip_ = tmp_path / "llama.zip"
    with zipfile.ZipFile(zip_, "w") as z:
        z.writestr("llama-b1/llama-server.exe", b"exe")
        z.writestr("llama-b1/ggml.dll", b"dll")
        z.writestr("llama-b1/README.md", b"leia")
        z.writestr("../../fora.dll", b"malicioso")
    instalar_llama(zip_, tmp_path / "llama")
    assert sorted(p.name for p in (tmp_path / "llama").iterdir()) == ["fora.dll", "ggml.dll", "llama-server.exe"]
    assert not (tmp_path.parent / "fora.dll").exists()


def test_obter_ia_baixa_os_dois_com_um_progresso_so(tmp_path, servidor, monkeypatch):
    base, partes, _ = servidor
    pacote = io.BytesIO()
    with zipfile.ZipFile(pacote, "w") as z:
        z.writestr("x/llama-server.exe", b"exe")
    ARQUIVOS["/llama.zip"] = pacote.getvalue()
    monkeypatch.setenv("MASCOTE_IA_DIR", str(tmp_path))
    monkeypatch.setattr(baixar, "LLAMA_FONTES", [[(base + "/llama.zip", len(pacote.getvalue()))]])
    monkeypatch.setattr(baixar, "LLAMA_TAMANHO", len(pacote.getvalue()))
    monkeypatch.setattr(baixar, "LLAMA_SHA256", hashlib.sha256(pacote.getvalue()).hexdigest())
    monkeypatch.setattr(baixar, "MODELO_FONTES", [partes])
    monkeypatch.setattr(baixar, "MODELO_TAMANHO", len(CONTEUDO))
    monkeypatch.setattr(baixar, "MODELO_SHA256", SHA)
    monkeypatch.setattr(baixar, "BLOB_OLLAMA", tmp_path / "sem-ollama")
    progresso = []
    baixar.obter_ia(lambda f, t: progresso.append((f, t)))
    total = len(pacote.getvalue()) + len(CONTEUDO)
    assert baixar.ia_instalada()
    assert progresso[-1] == (total, total) and all(t == total for _, t in progresso)
    assert [f for f, _ in progresso] == sorted(f for f, _ in progresso)
    assert sorted(p.name for p in (tmp_path / "llama").iterdir()) == ["llama-server.exe", "llama-server.exe.ok"]
