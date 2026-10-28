import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # testes não abrem janelas na tela

import pytest


@pytest.fixture(autouse=True)
def dados_temporarios(tmp_path, monkeypatch):
    monkeypatch.setenv("MASCOTE_DADOS", str(tmp_path / "dados"))
