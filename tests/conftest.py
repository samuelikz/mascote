import pytest


@pytest.fixture(autouse=True)
def dados_temporarios(tmp_path, monkeypatch):
    monkeypatch.setenv("MASCOTE_DADOS", str(tmp_path / "dados"))
