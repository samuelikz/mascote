from mascote import memoria


def test_memoria_adiciona_lista_apaga_e_ignora_duplicata():
    m = memoria.adicionar("Meu nome é Samuel")
    memoria.adicionar("  meu nome é samuel ")
    memoria.adicionar("")
    assert [x["fato"] for x in memoria.listar()] == ["Meu nome é Samuel"]
    memoria.apagar(m["id"])
    assert memoria.listar() == []
