import hashlib
import http.server
import threading

import pytest

from mascote import atualizar


def rel(tag, nome="MascoteSetup.exe", **extra):
    return {"tag_name": tag, "draft": False, "prerelease": False, "body": "notas",
            "assets": [{"name": nome, "browser_download_url": f"https://x/{tag}/{nome}", "size": 10,
                        "digest": "sha256:" + "a" * 64}], **extra}


def test_mais_nova():
    assert atualizar.mais_nova("v1.2.1", "1.2.0")
    assert atualizar.mais_nova("1.10.0", "1.9.9")
    assert not atualizar.mais_nova("v1.2.0", "1.2.0")
    assert not atualizar.mais_nova("ia-v1", "1.2.0")


def test_escolher_pega_a_mais_nova_e_ignora_ia_rascunho_e_sem_instalador():
    releases = [rel("ia-v1"), rel("v1.3.0", draft=True), rel("v1.2.5"), rel("v1.2.9", nome="outro.exe"),
                rel("v1.2.7"), rel("v1.1.0")]
    a = atualizar.escolher(releases, "1.2.0")
    assert a.versao == "1.2.7" and a.sha256 == "a" * 64 and a.url.endswith("v1.2.7/MascoteSetup.exe")


def test_escolher_em_dia():
    assert atualizar.escolher([rel("v1.2.0"), rel("ia-v1")], "1.2.0") is None


def test_escolher_instalador_de_teste():
    a = atualizar.escolher([rel("v1.2.1", nome="Mascote-teste-setup.exe")], "1.2.0", "Mascote-teste-setup.exe")
    assert a and a.versao == "1.2.1"


@pytest.fixture
def servidor():
    dados = b"setup" * 1000

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def log_message(self, *a):
            pass

    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}/s.exe", dados
    s.shutdown()


def test_baixar_confere_sha(servidor, tmp_path):
    url, dados = servidor
    ok = atualizar.Atualizacao("9.9.9", url, len(dados), hashlib.sha256(dados).hexdigest(), "")
    destino = atualizar.baixar(ok, lambda *a: None, pasta=tmp_path)
    assert destino.read_bytes() == dados
    ruim = atualizar.Atualizacao("9.9.8", url, len(dados), "0" * 64, "")
    with pytest.raises(ValueError):
        atualizar.baixar(ruim, lambda *a: None, pasta=tmp_path)
    assert not (tmp_path / "Mascote-9.9.8-setup.exe").exists()
