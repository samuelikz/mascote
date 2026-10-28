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
