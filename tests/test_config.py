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
