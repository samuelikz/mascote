from mascote import claude


def test_instalar_mantem_hooks_do_usuario_e_remover_tira_so_os_nossos():
    meu = {"hooks": [{"type": "command", "command": "echo oi"}]}
    dados = {"model": "x", "hooks": {"Stop": [meu]}}
    claude.instalar_ganchos(dados)
    claude.instalar_ganchos(dados)  # de novo: não duplica
    assert dados["hooks"]["Stop"][0] == meu and len(dados["hooks"]["Stop"]) == 2
    assert set(dados["hooks"]) == {"Stop", "UserPromptSubmit", "Notification"}
    assert "--claude pronto" in dados["hooks"]["Stop"][1]["hooks"][0]["command"]
    claude.remover_ganchos(dados)
    assert dados == {"model": "x", "hooks": {"Stop": [meu]}}


def test_gravar_evento_so_aceita_os_conhecidos():
    claude.gravar_evento("pronto")
    assert claude.arquivo_evento().read_text(encoding="utf-8") == "pronto"
    claude.gravar_evento("rm -rf")
    assert claude.arquivo_evento().read_text(encoding="utf-8") == "pronto"
