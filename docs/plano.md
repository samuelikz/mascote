# Mascote — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pet de desktop (bolinha verde no canto da tela) com Gemma 2 9B local, que come textos arrastados e vira lembretes/memórias/melhorias/traduções, chama pro almoço e conversa — empacotado num instalador Windows.

**Architecture:** App PySide6 de uma janela transparente sempre-por-cima. Lógica pura (agenda, memórias, prompts) em módulos testáveis sem Qt. A IA é um `llama-server.exe` (llama.cpp Vulkan) iniciado sob demanda como subprocesso e acessado por HTTP com `urllib`; chamadas rodam numa thread e devolvem por Signal Qt.

**Tech Stack:** Python 3.14 (`C:\Python314`), PySide6 6.12, pytest, sqlite3/json/urllib/ctypes (stdlib), llama.cpp `llama-server` build Vulkan win x64, PyInstaller 6.22 `--onedir`, Inno Setup 6.

**Spec:** `docs/design.md` — leia antes de cada tarefa.

## Global Constraints

- Só Windows 11. Todo texto visível ao usuário em português do Brasil.
- Personalidade: fofinho e brincalhão, frases curtas, emoji. Exemplo canônico: `ei, bora comer? 🍔`.
- Resultados de melhorar/traduzir vêm limpos (sem gracinha dentro do texto); a gracinha fica no balão em volta.
- Tradução: português → inglês; qualquer outra língua → português.
- Nenhuma dependência além de PySide6 (runtime) e pytest/pyinstaller (dev). HTTP via `urllib`.
- Sem Ollama em tempo de execução. Modelo em `recursos/modelo/gemma2-9b.gguf`, motor em `recursos/llama/llama-server.exe`.
- IA liga sob demanda e desliga após **300 s** sem uso. Animações, olhos, almoço e disparo de lembretes não dependem da IA.
- O pet nunca rouba foco do teclado, a não ser quando o balão de chat está aberto e o usuário clicou nele.
- Esconder em tela cheia (`QUNS_BUSY`=2, `QUNS_RUNNING_D3D_FULL_SCREEN`=3, `QUNS_PRESENTATION_MODE`=4); lembretes vencidos ficam na fila e aparecem ao sair.
- "Depois" adia **10 min**. Almoço padrão **12:00**, todo dia.
- Dados em `%LOCALAPPDATA%\Mascote\dados\` (variável `MASCOTE_DADOS` sobrescreve, usada nos testes). Instalação em `%LOCALAPPDATA%\Mascote\`, sem admin. "Iniciar com o Windows" marcado por padrão.
- Gemma 2 não aceita papel `system`: instruções vão no início do primeiro turno `user`.

## Review Focus

1. **Gemma devolve JSON com cercas ```json, texto antes/depois ou JSON quebrado** → extração ainda funciona ou cai em "pra quando? 🤔", nunca exceção. Teste na Tarefa 3.
2. **Repetição mensal no dia 31 (ou 29–31 em fevereiro)** → dispara no último dia do mês. Teste na Tarefa 2.
3. **PC desligado por dias com lembrete diário** → ao abrir, dispara **uma** vez e o próximo vai pro futuro, não uma enxurrada. Teste na Tarefa 2.
4. **`llama-server` não sobe (exe/modelo ausente, porta ocupada, Vulkan falha)** → erro em ≤ 60 s, pet faz cara triste com mensagem, app segue vivo. Teste na Tarefa 4.
5. **Texto arrastado gigante (ex.: 50 mil caracteres)** → truncado a 6000 caracteres antes de ir pro modelo (contexto 4096). Teste na Tarefa 3.

---

## Estrutura de arquivos

```
mascote/
  mascote/
    __init__.py
    __main__.py      # entrada: python -m mascote
    config.py        # pastas, config.json
    memoria.py       # memorias.json
    agenda.py        # lembretes (sqlite) + cálculo do próximo disparo
    prompts.py       # monta mensagens, interpreta respostas da Gemma
    ia.py            # ServidorIA (subprocesso llama-server) + Signal Qt
    janelas.py       # ctypes: tela cheia, tempo ocioso
    pet.py           # widget da bolinha (desenho, olhos, estados, drop)
    balao.py         # balão: fala, botões, chat, listas
    app.py           # liga tudo: timers, menu, fluxos
  tests/
  ferramentas/preparar_recursos.ps1
  instalador/mascote.iss
  build.ps1
  recursos/          # (gitignored) llama/ e modelo/
```

---

### Tarefa 1: Projeto, config e memórias

**Files:**
- Create: `mascote/__init__.py`, `mascote/config.py`, `mascote/memoria.py`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`
- Test: `tests/test_config.py`, `tests/test_memoria.py`, `tests/conftest.py`

**Interfaces:**
- Produces:
  - `config.PASTA_APP: Path` — pasta do exe quando `sys.frozen`, senão raiz do repo.
  - `config.RECURSOS: Path` = `PASTA_APP / "recursos"`
  - `config.pasta_dados() -> Path` — `MASCOTE_DADOS` ou `%LOCALAPPDATA%\Mascote\dados`; cria se faltar.
  - `config.carregar() -> dict` / `config.salvar(cfg: dict) -> None` — `config.json`; padrões `{"canto": "inf_dir", "ultima_comida": None}` mesclados com o arquivo.
  - `memoria.listar() -> list[dict]` (`{"id": int, "fato": str}`), `memoria.adicionar(fato: str) -> dict`, `memoria.apagar(id: int) -> None`. Ignora fato vazio/duplicado (comparação sem caixa e sem espaços nas pontas).

- [ ] **Step 1:** `git init`; `.gitignore` com `.venv/ recursos/ dist/ build/ __pycache__/ .superpowers/ *.spec`. `python -m venv .venv`; `requirements.txt` = `PySide6==6.12.0`; `requirements-dev.txt` = `-r requirements.txt`, `pytest`, `pyinstaller==6.22.3`. `.venv\Scripts\pip install -r requirements-dev.txt`.
- [ ] **Step 2: Testes que falham.** `conftest.py` tem fixture autouse que aponta `MASCOTE_DADOS` para `tmp_path`.

```python
def test_config_padroes_e_persistencia():
    assert config.carregar()["canto"] == "inf_dir"
    cfg = config.carregar(); cfg["canto"] = "sup_esq"; config.salvar(cfg)
    assert config.carregar()["canto"] == "sup_esq"

def test_config_arquivo_corrompido_volta_ao_padrao():
    (config.pasta_dados() / "config.json").write_text("{lixo", encoding="utf-8")
    assert config.carregar()["canto"] == "inf_dir"

def test_memoria_adiciona_lista_apaga_e_ignora_duplicata():
    m = memoria.adicionar("Meu nome é Samuel")
    memoria.adicionar("  meu nome é samuel ")
    memoria.adicionar("")
    assert [x["fato"] for x in memoria.listar()] == ["Meu nome é Samuel"]
    memoria.apagar(m["id"])
    assert memoria.listar() == []
```

- [ ] **Step 3:** `.venv\Scripts\python -m pytest tests -v` → FAIL (módulos não existem).
- [ ] **Step 4:** Implementar. JSON sempre `encoding="utf-8"`, `ensure_ascii=False`. Arquivo corrompido = padrão.
- [ ] **Step 5:** Pytest → PASS.
- [ ] **Step 6:** `git add -A; git commit -m "feat: config e memórias"`

---

### Tarefa 2: Agenda de lembretes

**Files:**
- Create: `mascote/agenda.py`
- Test: `tests/test_agenda.py`

**Interfaces:**
- Produces:
  - Regra de repetição (`dict | None`): `None` (uma vez), `{"tipo": "diario"}`, `{"tipo": "semanal", "dias": [0..6]}` (0 = segunda), `{"tipo": "mensal", "dia": 1..31}`.
  - `proximo_disparo(base: datetime, regra: dict, depois_de: datetime) -> datetime` — primeira ocorrência da regra, na hora:minuto de `base`, estritamente depois de `depois_de`. Mensal com dia inexistente → último dia do mês.
  - `class Agenda(caminho: Path)` (sqlite):
    - `adicionar(texto: str, quando: datetime, regra: dict | None = None) -> int`
    - `vencidos(agora: datetime) -> list[Lembrete]`
    - `feito(id: int, agora: datetime) -> None` — sem regra: apaga; com regra: `proximo = proximo_disparo(original, regra, agora)`.
    - `adiar(id: int, agora: datetime, minutos: int = 10) -> None` — só muda `proximo`; mantém `original` e regra.
    - `listar() -> list[Lembrete]` (por `proximo`), `apagar(id: int) -> None`
    - `garantir_almoco(hora: str = "12:00") -> None` — cria, se não existir, um lembrete diário com texto `ALMOCO` (marcador fixo; o app troca pela fala `ei, bora comer? 🍔`).
  - `@dataclass Lembrete(id: int, texto: str, original: datetime, proximo: datetime, regra: dict | None)`
  - Colunas: `id, texto, original, proximo, regra_json`. Datas em ISO local sem fuso.

- [ ] **Step 1: Testes que falham.**

```python
D = datetime
def test_diario_pula_dias_perdidos():  # Review Focus 3
    assert proximo_disparo(D(2026,10,1,9), {"tipo":"diario"}, D(2026,10,20,15)) == D(2026,10,21,9)

def test_semanal_seg_a_sex_pula_fim_de_semana():
    regra = {"tipo":"semanal","dias":[0,1,2,3,4]}
    assert proximo_disparo(D(2026,10,30,9), regra, D(2026,10,30,10)) == D(2026,11,2,9)  # sex → seg

def test_mensal_dia_31_em_fevereiro_e_novembro():  # Review Focus 2
    regra = {"tipo":"mensal","dia":31}
    assert proximo_disparo(D(2026,1,31,8), regra, D(2026,2,1)) == D(2026,2,28,8)
    assert proximo_disparo(D(2026,1,31,8), regra, D(2026,11,1)) == D(2026,11,30,8)

def test_feito_unico_apaga_e_repetido_reagenda_uma_vez(tmp_path):
    a = Agenda(tmp_path/"a.db")
    u = a.adicionar("boleto", D(2026,10,1,9))
    r = a.adicionar("remédio", D(2026,10,1,9), {"tipo":"diario"})
    assert {l.id for l in a.vencidos(D(2026,10,20,15))} == {u, r}
    a.feito(u, D(2026,10,20,15)); a.feito(r, D(2026,10,20,15))
    assert [l.proximo for l in a.listar()] == [D(2026,10,21,9)]
    assert a.vencidos(D(2026,10,20,16)) == []

def test_adiar_mantem_regra(tmp_path):
    a = Agenda(tmp_path/"a.db")
    r = a.adicionar("água", D(2026,10,27,9), {"tipo":"diario"})
    a.adiar(r, D(2026,10,27,9,1))
    l = a.listar()[0]
    assert l.proximo == D(2026,10,27,9,11) and l.regra == {"tipo":"diario"}
    a.feito(r, D(2026,10,27,9,12))
    assert a.listar()[0].proximo == D(2026,10,28,9)

def test_garantir_almoco_idempotente(tmp_path):
    a = Agenda(tmp_path/"a.db"); a.garantir_almoco(); a.garantir_almoco()
    assert [(l.texto, l.regra) for l in a.listar()] == [("ALMOCO", {"tipo":"diario"})]
```

- [ ] **Step 2:** Pytest → FAIL.
- [ ] **Step 3:** Implementar. `proximo_disparo`: itera dia a dia a partir de `depois_de.date()` (no máximo 400 dias) até achar dia válido com `datetime(dia, hora de base) > depois_de`; mensal compara com `min(dia, último_dia_do_mês)` via `calendar.monthrange`. `garantir_almoco` cria com `original` = hoje no horário dado.
- [ ] **Step 4:** Pytest → PASS.
- [ ] **Step 5:** Commit `feat: agenda de lembretes com repetição`.

---

### Tarefa 3: Prompts e interpretação das respostas

**Files:**
- Create: `mascote/prompts.py`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Consumes: formato de regra da Tarefa 2.
- Produces:
  - `LIMITE = 6000`; `truncar(texto: str) -> str` — corta em `LIMITE` e acrescenta `"…"`.
  - `mensagens_chat(historico: list[dict], memorias: list[str], agora: datetime) -> list[dict]` — `historico` no formato OpenAI (`role` user/assistant). Injeta no início do primeiro `user` o bloco de personalidade + memórias + data/hora; nunca devolve `role: system`. Mantém só as últimas 12 mensagens do histórico.
  - `mensagens_extrair(texto: str, agora: datetime) -> list[dict]` — pede só JSON `{"texto", "quando", "repete"}` (formato de `repete` = regra da Tarefa 2, `quando` em ISO ou null), com data, hora e dia da semana atuais por extenso.
  - `ler_extracao(resposta: str) -> tuple[str, datetime | None, dict | None] | None` — pega o primeiro `{...}` balanceado na resposta; JSON inválido/sem `texto` → `None`; `quando` inválido → `None` no segundo item; regra fora do formato → `None` no terceiro.
  - `mensagens_melhorar(texto: str) -> list[dict]`, `mensagens_traduzir(texto: str) -> list[dict]` — pedem só o texto final, sem comentário. Traduzir: "se estiver em português, traduza para inglês; senão, para português".
  - `separar_memoria(resposta: str) -> tuple[str, list[str]]` — o prompt de chat instrui a Gemma a terminar com linhas `MEMORIA: <fato>` quando o usuário contar algo durável sobre si; esta função remove essas linhas e devolve os fatos.
  - Todas as funções `mensagens_*` aplicam `truncar` ao texto do usuário.

- [ ] **Step 1: Testes que falham.**

```python
AGORA = datetime(2026,10,27,22,0)
def test_extracao_com_cercas_e_texto_em_volta():  # Review Focus 1
    r = 'Claro! ```json\n{"texto":"pagar boleto","quando":"2026-10-28T09:00","repete":null}\n``` 😊'
    assert ler_extracao(r) == ("pagar boleto", datetime(2026,10,28,9,0), None)

def test_extracao_quebrada_ou_sem_hora():
    assert ler_extracao("não entendi 😅") is None
    assert ler_extracao('{"texto": "x", "quando": ') is None
    assert ler_extracao('{"texto":"ligar","quando":"sexta","repete":{"tipo":"anual"}}') == ("ligar", None, None)

def test_extracao_semanal():
    r = '{"texto":"academia","quando":"2026-10-28T07:00","repete":{"tipo":"semanal","dias":[0,2,4]}}'
    assert ler_extracao(r)[2] == {"tipo":"semanal","dias":[0,2,4]}

def test_texto_gigante_truncado():  # Review Focus 5
    msgs = mensagens_melhorar("a" * 50_000)
    assert len(msgs[-1]["content"]) < 8000

def test_chat_sem_role_system_e_com_memorias():
    msgs = mensagens_chat([{"role":"user","content":"oi"}], ["Meu nome é Samuel"], AGORA)
    assert all(m["role"] != "system" for m in msgs)
    assert "Meu nome é Samuel" in msgs[0]["content"] and msgs[0]["content"].endswith("oi")

def test_separar_memoria():
    assert separar_memoria("Prazer, Samuel! 😄\nMEMORIA: nome é Samuel") == ("Prazer, Samuel! 😄", ["nome é Samuel"])
```

- [ ] **Step 2:** Pytest → FAIL.
- [ ] **Step 3:** Implementar. Textos dos prompts em português; personalidade copia o tom do spec com o exemplo `ei, bora comer? 🍔`.
- [ ] **Step 4:** Pytest → PASS.
- [ ] **Step 5:** Commit `feat: prompts e leitura das respostas`.

---

### Tarefa 4: Recursos e servidor de IA

**Files:**
- Create: `ferramentas/preparar_recursos.ps1`, `mascote/ia.py`
- Test: `tests/test_ia.py`

**Interfaces:**
- Consumes: `config.RECURSOS`.
- Produces:
  - `class ErroIA(Exception)`
  - `class ServidorIA(exe: Path, modelo: Path, ocioso_s: int = 300, timeout_s: int = 60)`:
    - `perguntar(mensagens: list[dict], max_tokens: int = 512) -> str` — bloqueante; liga se preciso (`garantir_ligado`), POST `/v1/chat/completions` (`temperature` 0.7), atualiza `ultimo_uso`.
    - `garantir_ligado() -> None` — porta livre via socket bind em `127.0.0.1:0`; `Popen([exe, "-m", modelo, "--host", "127.0.0.1", "--port", p, "-ngl", "99", "-c", "4096"], creationflags=CREATE_NO_WINDOW)`; espera `GET /health` = 200; processo morreu ou passou `timeout_s` → mata e levanta `ErroIA`. Exe/modelo inexistente → `ErroIA` imediato.
    - `desligar_se_ocioso(agora: float) -> None`, `desligar() -> None`, `ligado: bool`
  - `class PonteIA(QObject)` com `pronto = Signal(str, object)` e `falhou = Signal(str, object)`; `pedir(mensagens, etiqueta: object, max_tokens=512)` roda `perguntar` numa `threading.Thread(daemon=True)` e emite o Signal (o receptor na thread principal recebe por conexão enfileirada). Um pedido por vez: lock em `ServidorIA.perguntar`.
  - `ServidorIA.padrao() -> ServidorIA` usando `RECURSOS/"llama"/"llama-server.exe"` e `RECURSOS/"modelo"/"gemma2-9b.gguf"`.

- [ ] **Step 1: `preparar_recursos.ps1`.** Cria `recursos\llama` e `recursos\modelo`. Baixa da API do GitHub (`repos/ggml-org/llama.cpp/releases/latest`) o asset `llama-*-bin-win-vulkan-x64.zip`, extrai em `recursos\llama`, grava a tag em `recursos\llama\VERSAO.txt`. Copia `$env:USERPROFILE\.ollama\models\blobs\sha256-ff1d1fc78170d787ee1201778e2dd65ea211654ca5fb7d69b5a2e7b123a50373` para `recursos\modelo\gemma2-9b.gguf` (se não existir, lê o manifesto `...\manifests\registry.ollama.ai\library\gemma2\9b` e pega a camada `application/vnd.ollama.image.model`). Idempotente.
- [ ] **Step 2:** Rodar o script; conferir `recursos\llama\llama-server.exe` e o `.gguf` de ~5,4 GB.
- [ ] **Step 3: Testes que falham.**

```python
def test_exe_inexistente_falha_rapido(tmp_path):  # Review Focus 4
    s = ServidorIA(tmp_path/"nao.exe", tmp_path/"nao.gguf")
    with pytest.raises(ErroIA): s.perguntar([{"role":"user","content":"oi"}])
    assert not s.ligado

def test_processo_que_morre_vira_erro(tmp_path):  # Review Focus 4
    s = ServidorIA(Path(sys.executable), tmp_path/"x.gguf", timeout_s=10)  # python sai com erro nos args
    (tmp_path/"x.gguf").write_bytes(b"")
    t = time.time()
    with pytest.raises(ErroIA): s.garantir_ligado()
    assert time.time() - t < 10

@pytest.mark.skipif(not ServidorIA.padrao().disponivel(), reason="recursos/ ausente")
def test_gemma_de_verdade_responde_e_desliga():
    s = ServidorIA.padrao(ocioso_s=0)
    assert s.perguntar([{"role":"user","content":"Responda só: oi"}], max_tokens=16).strip()
    s.desligar_se_ocioso(time.time() + 1)
    assert not s.ligado
```

  (Adiciona `disponivel() -> bool` = exe e modelo existem; `padrao(**kw)` repassa kwargs.)
- [ ] **Step 4:** Pytest → FAIL.
- [ ] **Step 5:** Implementar.
- [ ] **Step 6:** Pytest → PASS, inclusive o teste real (com Ollama **fechado** para liberar a placa de vídeo: `ollama stop gemma2:9b`). Anotar no commit o tempo da primeira resposta.
- [ ] **Step 7:** Commit `feat: servidor de IA local sob demanda`.

---

### Tarefa 5: Sinais do Windows

**Files:**
- Create: `mascote/janelas.py`
- Test: `tests/test_janelas.py`

**Interfaces:**
- Produces: `tela_cheia() -> bool` (`shell32.SHQueryUserNotificationState` ∈ {2, 3, 4}); `segundos_ocioso() -> float` (`user32.GetLastInputInfo` + `kernel32.GetTickCount64`). Qualquer falha de ctypes → `False` / `0.0`.

- [ ] **Step 1: Teste que falha.**

```python
def test_sinais_retornam_tipos_certos():
    assert isinstance(tela_cheia(), bool)
    assert 0.0 <= segundos_ocioso() < 86400 * 30
```

- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** PASS.
- [ ] **Step 5:** Manual: `python -c "import time,mascote.janelas as j; time.sleep(5); print(j.tela_cheia())"` com um vídeo do YouTube em tela cheia → `True`.
- [ ] **Step 6:** Commit `feat: detecção de tela cheia e ociosidade`.

---

### Tarefa 6: A bolinha (widget do pet)

**Files:**
- Create: `mascote/pet.py`
- Test: `tests/test_pet.py`

**Interfaces:**
- Produces:
  - `pupila(centro: QPointF, mouse: QPointF, raio: float) -> QPointF` — deslocamento da pupila, direção do mouse, módulo `min(raio, distância/20)`.
  - `canto_mais_proximo(pos: QPoint, area: QRect) -> str` ∈ `"sup_esq" | "sup_dir" | "inf_esq" | "inf_dir"`; `posicao_do_canto(canto: str, area: QRect, tamanho: QSize, margem=12) -> QPoint`.
  - `class Pet(QWidget)`: janela `FramelessWindowHint | WindowStaysOnTopHint | Tool | WindowDoesNotAcceptFocus`, `WA_TranslucentBackground`, `WA_ShowWithoutActivating`, ~120×120 (corpo 80 px).
    - Estados `Estado = Literal["parado","pulo","cochilo","boca","pensando","feliz","triste","fome","chamando"]`; `definir_estado(e: Estado, ms: int | None = None)` (volta a `parado` depois de `ms`).
    - Signals: `clicado()`, `clique_direito(QPoint)`, `comeu(str)` (texto solto em cima), `mudou_canto(str)`.
    - Timer 33 ms: lê `QCursor.pos()`, atualiza pupilas, respiração (escala Y ±3% em 3 s), pulinho quando o mouse entra num raio de 150 px (no máx. 1 a cada 4 s), squash & stretch no pulo.
    - Arrastar com botão esquerdo move; ao soltar, encaixa em `canto_mais_proximo` da `availableGeometry` da tela em que está e emite `mudou_canto`.
    - Drop: `dragEnterEvent` aceita `hasText()` e põe `boca`; `dropEvent` emite `comeu(texto)`.
    - Caretas (olhos e boca desenhados com `QPainter`): parado `ᴗ`, pulo/feliz `◡` e olhos em arco, cochilo olhos fechados + "z z", boca `O`, pensando olhos para cima + "…", triste boca invertida, fome boca ondulada + gotinha, chamando `▽`. Cor do corpo `#8fd3a8`.

- [ ] **Step 1: Testes que falham.**

```python
def test_pupila_limitada_ao_raio():
    p = pupila(QPointF(0,0), QPointF(1000,0), 4)
    assert abs(p.x() - 4) < 1e-6 and p.y() == 0
    assert pupila(QPointF(0,0), QPointF(0,0), 4) == QPointF(0,0)

def test_canto_mais_proximo():
    area = QRect(0,0,1920,1040)
    assert canto_mais_proximo(QPoint(1800,900), area) == "inf_dir"
    assert canto_mais_proximo(QPoint(10,10), area) == "sup_esq"
```

- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** PASS.
- [ ] **Step 5:** Manual: um `if __name__ == "__main__"` em `pet.py` abre só o pet em `inf_dir` com um menu de teste que percorre os estados. Conferir: fundo transparente, olhos seguem o mouse, pula ao chegar perto, digitar no Bloco de Notas com o pet visível não perde foco, arrastar texto do Chrome até ele faz `boca` e imprime o texto.
- [ ] **Step 6:** Commit `feat: bolinha animada que observa o mouse`.

---

### Tarefa 7: O balão

**Files:**
- Create: `mascote/balao.py`

**Interfaces:**
- Produces: `class Balao(QWidget)` (sem moldura, sempre por cima, `Tool`, ancorado acima/ao lado do pet conforme o canto, sem sair da tela; largura máx. 320 px).
  - `falar(texto: str, botoes: list[tuple[str, object]] = [], ms: int | None = 6000)` — botões emitem `escolheu(object)`; com botões, não some sozinho.
  - `mostrar_resultado(texto: str)` — texto selecionável + botão `copiar 📋` (QClipboard) + `fechar`.
  - `abrir_chat(historico: list[dict])` — histórico rolável + `QLineEdit` (aqui pode pegar foco); Enter emite `enviou(str)`; Esc fecha.
  - `mostrar_lista(titulo: str, itens: list[tuple[object, str]])` — cada item com `✕` que emite `apagar(object)`.
  - `posicionar(pet_geo: QRect, canto: str)`.
  - Signals: `escolheu(object)`, `enviou(str)`, `apagar(object)`, `fechou()`.
- Sem teste automático (UI pura); verificação manual no Step 2.

- [ ] **Step 1:** Implementar. Visual: fundo branco, cantos 12 px, sombra, fonte Segoe UI 10, texto `#222`.
- [ ] **Step 2:** Manual via `__main__` de `balao.py`: os quatro modos aparecem, `copiar` coloca o texto no clipboard, balão perto do canto `sup_dir` não sai da tela.
- [ ] **Step 3:** Commit `feat: balão de fala e chat`.

---

### Tarefa 8: Juntando tudo

**Files:**
- Create: `mascote/app.py`, `mascote/__main__.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: tudo acima.
- Produces: `class App(QObject)` com `iniciar()`; `__main__.py` cria `QApplication`, `App(...).iniciar()`, `exec()`. Instância única: `QLockFile(pasta_dados()/"mascote.lock")`; se já houver uma rodando, sai.
- `escolher_fala_lembrete(l: Lembrete) -> str` — `ALMOCO` → `ei, bora comer? 🍔`; outros → `ei! hora de {texto} 💡`.

Fluxos (todos no `App`):
- **Início:** `Agenda(pasta_dados()/"agenda.db")`, `garantir_almoco()`, pet no canto salvo, checa vencidos imediatamente.
- **Timer 20 s:** se `tela_cheia()` → esconde pet e balão; senão mostra. Fora da tela cheia e sem lembrete na tela → pega o primeiro de `vencidos(agora)`: pet `chamando`, balão `falar(escolher_fala_lembrete(l), [("feito ✅", ("feito", id)), ("depois ⏰", ("adiar", id))], ms=None)`. Feito → `agenda.feito` + `feliz` 2 s. Depois → `agenda.adiar`.
  Também: `segundos_ocioso() > 600` → `cochilo`; mexeu → `parado`. `ultima_comida` há mais de 4 h → `fome` (só quando parado). `servidor.desligar_se_ocioso(time.time())`.
- **Comeu(texto):** `ultima_comida = agora`, balão com `lembrar 📌 / guardar 🧠 / melhorar ✨ / traduzir 🌎`.
  - lembrar → `pensando` → `mensagens_extrair` → `ler_extracao`. Sem resultado → `não entendi 😅 tenta pelo chat?`. Sem `quando` → `pra quando? 🤔` e abre chat; a próxima mensagem vai de novo para `mensagens_extrair` com `"{texto} — {resposta}"`. Com `quando` → `agenda.adicionar`, `feliz`, `Nhac! 😋 vou te lembrar {quando formatado}` (ex.: `amanhã às 9h`, `toda segunda às 7h`).
  - guardar → `memoria.adicionar(truncar(texto))`, `feliz`, `guardei! 🧠`.
  - melhorar / traduzir → `pensando` → `balao.mostrar_resultado(resposta)`.
- **Clique:** abre chat. Mensagem → `mensagens_chat(historico, fatos, agora)` → `separar_memoria` → fatos vão para `memoria.adicionar`, texto para o balão. Se a mensagem começar com "me lembra", vai pelo fluxo `lembrar`. Histórico só em memória (some ao fechar o app).
- **Clique direito:** `QMenu` com: `Ver lembretes` (`mostrar_lista`, ✕ apaga; almoço mostra `almoço 🍔 12:00`), `O que eu lembro de você` (`mostrar_lista` das memórias), `Horário do almoço…` (`QInputDialog` HH:MM → atualiza `original`/`proximo` do lembrete `ALMOCO`), `Sair`.
- **Erro da IA (`falhou`):** `triste` 4 s + `ai, minha cabecinha falhou 😵 tenta de novo?`. Nunca derruba o app.
- **mudou_canto:** salva em config.

- [ ] **Step 1: Teste que falha.**

```python
def test_fala_do_almoco_e_lembrete():
    D = datetime(2026,10,27,12)
    assert escolher_fala_lembrete(Lembrete(1,"ALMOCO",D,D,{"tipo":"diario"})) == "ei, bora comer? 🍔"
    assert escolher_fala_lembrete(Lembrete(2,"pagar boleto",D,D,None)) == "ei! hora de pagar boleto 💡"
```

- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** PASS (suite inteira).
- [ ] **Step 5: Verificação manual** com `.venv\Scripts\python -m mascote` (Ollama fechado):
  1. Pet aparece no canto inferior direito, observando.
  2. Arrastar "pagar boleto amanhã às 9h" do Bloco de Notas → lembrar → `Nhac! 😋 …`; aparece em `Ver lembretes`.
  3. Pelo chat: `me lembra de beber água daqui 2 minutos` → em ~2 min chama; `depois` volta 10 min mais tarde.
  4. `toda segunda às 7h academia` → lista mostra repetição.
  5. Chat: `meu nome é Samuel` → depois `O que eu lembro de você` lista.
  6. Arrastar um parágrafo em inglês → traduzir → português com `copiar 📋`.
  7. Vídeo em tela cheia → pet some; sair → volta.
  8. Renomear `recursos\modelo` e tentar conversar → cara triste, app vivo. Desfazer.
  9. Após 5 min sem usar, `llama-server.exe` some do Gerenciador de Tarefas.
- [ ] **Step 6:** Commit `feat: pet completo`.

---

### Tarefa 9: Instalador

**Files:**
- Create: `build.ps1`, `instalador/mascote.iss`, `instalador/icone.ico`

**Interfaces:**
- Consumes: `python -m mascote` como entrada; `recursos/`.

- [ ] **Step 1:** `winget install JRSoftware.InnoSetup` (se `iscc` não estiver no PATH, usar `${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe` ou `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`).
- [ ] **Step 2:** `icone.ico` gerado desenhando a bolinha com `QPainter` num `QImage` 256 px (script único em `build.ps1` via `python -c`), salvo como `.ico`.
- [ ] **Step 3:** `build.ps1`: roda pytest (para se falhar); `pyinstaller --noconfirm --onedir --windowed --name Mascote --icon instalador\icone.ico mascote\__main__.py`; copia `recursos\` para `dist\Mascote\recursos\`; roda `ISCC instalador\mascote.iss`.
- [ ] **Step 4:** `mascote.iss`: `PrivilegesRequired=lowest`, `DefaultDirName={localappdata}\Mascote`, `DisableDirPage=yes`, fontes `dist\Mascote\*` recursivo, `DiskSpanning` desligado mas `Compression=lzma2/fast` (modelo já é comprimido; usar `Flags: nocompression` no `.gguf`), atalho no Menu Iniciar, tarefa `iniciar` "Iniciar com o Windows" **marcada** → atalho em `{userstartup}`, `[Run]` abre o pet ao terminar, `[UninstallDelete]` **não** apaga `dados\`. Saída `dist\MascoteSetup.exe`.
- [ ] **Step 5: Verificação:** `.\build.ps1` termina sem erro; instalar `MascoteSetup.exe` sem admin; pet abre sozinho; reiniciar o Windows → pet volta; com o Ollama desinstalado ou parado, conversar funciona; desinstalar e reinstalar → lembretes e memórias continuam lá.
- [ ] **Step 6:** Commit `build: instalador do Mascote`.
