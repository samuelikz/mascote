import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # testes não abrem janelas na tela

import pytest


@pytest.fixture(autouse=True)
def dados_temporarios(tmp_path, monkeypatch):
    monkeypatch.setenv("MASCOTE_DADOS", str(tmp_path / "dados"))


@pytest.fixture(autouse=True)
def registro_temporario(monkeypatch):
    import winreg

    chave = rf"Software\MascoteTeste{os.getpid()}"
    monkeypatch.setenv("MASCOTE_REGISTRO", chave)
    yield
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, chave)
    except OSError:
        pass
