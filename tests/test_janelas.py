from mascote.janelas import segundos_ocioso, tela_cheia


def test_sinais_retornam_tipos_certos():
    assert isinstance(tela_cheia(), bool)
    assert 0.0 <= segundos_ocioso() < 86400 * 30
