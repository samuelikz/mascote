import pytest

from mascote import config


def test_config_padroes_e_persistencia():
    assert config.carregar()["canto"] == "inf_dir"
    cfg = config.carregar()
    cfg["canto"] = "sup_esq"
    config.salvar(cfg)
    assert config.carregar()["canto"] == "sup_esq"


def test_config_arquivo_corrompido_volta_ao_padrao():
    (config.pasta_dados() / "config.json").write_text("{lixo", encoding="utf-8")
    assert config.carregar()["canto"] == "inf_dir"


def test_gravacao_interrompida_nao_estraga_o_arquivo(monkeypatch):  # revisão #9
    import pathlib

    config.gravar_json(config.pasta_dados() / "memorias.json", [{"id": 1, "fato": "importante"}])
    original = pathlib.Path.write_text

    def queda_de_energia(self, texto, *a, **kw):
        original(self, texto[: len(texto) // 2], *a, **kw)
        raise OSError("faltou luz")

    monkeypatch.setattr(pathlib.Path, "write_text", queda_de_energia)
    with pytest.raises(OSError):
        config.gravar_json(config.pasta_dados() / "memorias.json", [{"id": 1, "fato": "importante"}, {"id": 2, "fato": "x"}])
    monkeypatch.setattr(pathlib.Path, "write_text", original)  # undo() desfaria também o MASCOTE_DADOS
    assert config.ler_json(config.pasta_dados() / "memorias.json", []) == [{"id": 1, "fato": "importante"}]


def test_preferencias_do_instalador_com_padroes():
    assert config.preferencias() == {"Nome": "Mascote", "IA": "embutida", "ModeloOllama": "gemma2:9b"}
    config.salvar_preferencia("Nome", "Bolinha")
    config.salvar_preferencia("IA", "ollama")
    config.salvar_preferencia("ModeloOllama", "  ")
    assert config.preferencias() == {"Nome": "Bolinha", "IA": "ollama", "ModeloOllama": "gemma2:9b"}


def test_ia_desconhecida_vira_embutida():
    config.salvar_preferencia("IA", "qualquer")
    assert config.preferencias()["IA"] == "embutida"


def test_identidade_vem_da_pasta_instalada(monkeypatch):
    import sys

    assert config.identidade() == "Mascote"  # rodando do código-fonte
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Users\x\AppData\Local\Programs\MascoteTeste\Mascote.exe")
    assert config.identidade() == "MascoteTeste"
    monkeypatch.setattr(sys, "executable", r"D:\outro lugar\Mascote.exe")
    assert config.identidade() == "Mascote"
    monkeypatch.delenv("MASCOTE_DADOS")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\nao-existe-mascote")
    monkeypatch.setattr(sys, "executable", r"C:\P\MascoteTeste\Mascote.exe")
    monkeypatch.setattr(config.Path, "mkdir", lambda *a, **k: None)
    assert str(config.pasta_dados()).endswith(r"MascoteTeste\dados")
