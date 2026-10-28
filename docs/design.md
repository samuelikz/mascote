# Mascote — design

Data: 2026-10-27 · Autor: Samuel (com Claude)

## Intenção

Um bichinho virtual que mora num canto da área de trabalho do Windows, fofo e brincalhão, com IA local (Gemma 2 9B) sem depender de internet nem do Ollama rodando. Ele serve de companhia e de ajudante leve: lembra das tarefas que o Samuel "dá de comer" a ele, chama pro almoço, conversa, melhora mensagens e traduz textos. O valor está no charme (caretas, pulinhos, jeito de falar) somado à utilidade do dia a dia, sem nunca virar um estorvo na tela.

## Objetivos

1. **Pet no canto que observa.** Fica parado num canto da tela; só os olhos seguem o cursor do mouse. *(decisão do Samuel)*
2. **Animações e caretas.** Respira devagar parado, dá pulinho quando o mouse chega perto, cochila se o PC fica ocioso muito tempo, abre a boca quando recebe comida, pula pra chamar atenção. Caretas no estilo de expressões de emoji, desenhadas no rosto. *(Samuel pediu animações/caretas; a lista de estados foi proposta minha e aprovada)*
3. **Comida = qualquer texto arrastado.** Arrastar um texto selecionado de qualquer app até o pet → ele "come" e mostra botões rápidos no balão: **lembrar 📌 / guardar 🧠 / melhorar ✨ / traduzir 🌎**. *(Samuel decidiu: botões rápidos, e nem toda comida é lembrete — pode ser algo que ele quer que o pet saiba)*
   - **lembrar 📌:** a IA extrai o que lembrar, quando e se repete. Sem horário claro, ele pergunta no balão ("pra quando? 🤔").
   - **guardar 🧠:** vira memória (mesmo arquivo do objetivo 7), sem horário.
   - **melhorar ✨ / traduzir 🌎:** resultado no balão com botão de copiar. Tradução: português → inglês; qualquer outra língua → português *(minha decisão)*.
   - Também dá pra fazer tudo isso digitando/colando no chat ("me lembra de X sexta às 14h"). Isso cobre apps que não deixam arrastar texto. *(minha decisão)*
4. **Lembretes, únicos ou repetidos.** *(Samuel pediu repetição)* Suporta: uma vez, todo dia, dias da semana escolhidos ("toda segunda", "seg a sex"), todo mês num dia *(os tipos de repetição são minha decisão)*. Na hora certa ele pula e mostra balão com **feito** (fica feliz; se repete, agenda a próxima) e **depois** (adia 10 min). "Ver lembretes" lista e permite apagar. Lembretes que venceram com o PC desligado ou com o pet fechado aparecem assim que ele abrir; durante tela cheia ficam na fila e aparecem ao sair dela *(minha decisão)*. "Iniciar com o Windows" vem ligado por padrão *(minha decisão)*.
5. **Almoço.** Todo dia às 12:00 chama: "ei, bora comer? 🍔". Horário configurável. *(aprovado)*
6. **Conversa.** Clique no pet abre um balão de chat colado nele. Bate-papo, "melhora essa mensagem", "traduz pro inglês"; respostas com botão de copiar. *(Samuel pediu)*
7. **Aprende com você.** Guarda fatos que o Samuel conta (nome, horários, preferências de tom) num arquivo de memórias e usa nas conversas. "O que você lembra de mim?" lista; dá pra apagar itens. Não é treino do modelo. *(Samuel pediu "aprender"; a forma — memória de fatos — foi proposta minha e aprovada)*
8. **Fome de charme.** Muito tempo sem tarefa → carinha de fome. Sem punição. *(aprovado)*
9. **Instalável com pasta própria.** Instalador coloca tudo em uma pasta do pet (programa, modelo, lembretes, memórias) e cria atalho. *(Samuel pediu)*

## Personalidade

Fofinho e brincalhão, frases curtas, emoji. Exemplo canônico do Samuel: **"ei, bora comer? 🍔"**. Responde em português do Brasil por padrão. Em tarefas de texto (melhorar/traduzir), entrega o texto pronto, limpo, sem gracinha dentro do resultado — a gracinha fica no balão em volta.

## Visual

"Bolinha fofa": gosminha verde redonda que estica/achata ao pular (squash & stretch). Olhos (branco + pupila que segue o mouse) e boca desenhados — caretas = trocar forma de olhos/boca. Sem bordas de janela, fundo transparente, sempre por cima. Tamanho ~70–90 px. Referência: mockups em `.superpowers/brainstorm/716-1793149062/content/` (`pet-na-tela.html`, `comportamento-v2.html`).

## Não-objetivos

- Não anda pela tela nem segue o mouse com o corpo.
- Não treina/afina o modelo.
- Não sincroniza com nuvem, celular ou agenda do Google.
- Não é multiusuário nem multiplataforma: só Windows 11, só este PC.

## Anti-objetivos (falhou mesmo que funcione)

- **Ficar no caminho.** Seguir o mouse, cobrir o que o Samuel está fazendo, roubar foco do teclado, aparecer em cima de jogo/vídeo em tela cheia. *(o Samuel disse explicitamente que seguir o mouse irritaria)*
- **Pesar no PC o tempo todo.** Deixar 6 GB presos na placa de vídeo enquanto ninguém fala com ele.
- **Perder lembrete.** Um lembrete aceito que nunca dispara é pior que não ter o recurso.
- **Ser seco/robótico** no balão.

## Restrições

- **Hardware do Samuel (medido):** Ryzen 7 5700G, 32 GB RAM, **AMD RX 580 8 GB** (sem CUDA, sem ROCm no Windows), ~44 GB livres em C:. Gemma 2 9B via Ollama nesta máquina: ~12,6 tokens/s com 97% na GPU, ~10 s de carga a frio.
- **Sem Ollama em tempo de execução.** O pet traz o próprio motor e o próprio modelo. *(Samuel pediu)*
- Modelo já existe localmente no Ollama (`gemma2:9b`, 5,4 GB, Q4_0) — o blob GGUF em `%USERPROFILE%\.ollama\models\blobs\` pode ser copiado; não precisa baixar de novo.
- Python 3.14 instalado em `C:\Python314`.

## Como — decidido

Decisões técnicas são **minhas** (o Samuel deixou comigo), não dele:

- **Motor de IA:** `llama-server.exe` do llama.cpp, build oficial **Vulkan** para Windows (funciona na RX 580), empacotado na pasta do pet e iniciado pelo pet como subprocesso em `127.0.0.1` numa porta livre. O pet fala com ele pela API HTTP compatível com OpenAI (`/v1/chat/completions`). Motivo: evita compilar `llama-cpp-python` com Vulkan no Windows.
- **Carregar sob demanda.** O servidor de IA sobe quando há conversa ou comida pra digerir e é encerrado após ~5 min sem uso. Animações, olhos, almoço e disparo de lembretes **não** dependem da IA. Durante a carga (~10 s) o pet mostra carinha de "pensando".
- **App:** Python + **PySide6** (janela sem moldura, transparente, sempre por cima, `Tool` pra não aparecer na barra de tarefas; desenho com `QPainter`; drag-and-drop de texto nativo).
- **Dados:** `sqlite3` (stdlib) para lembretes; `memorias.json` para fatos do usuário; `config.json` (canto, horário do almoço, etc.).
- **Extração de lembrete:** prompt pede à Gemma JSON `{"texto": ..., "quando": "ISO-8601" | null, "repete": null | {"tipo": "diario" | "semanal" | "mensal", "dias": [0-6] (semanal, 0=seg) | dia_do_mes (mensal)}}`, passando data/hora e dia da semana atuais. JSON inválido ou `quando` nulo → pet pergunta no balão. Tabela guarda `proximo_disparo` + regra de repetição; ao marcar "feito", calcula o próximo. Isso tem que vir com teste do cálculo do próximo disparo (fim de mês, virada de semana).
- **Gemma 2 não tem papel `system`:** instruções de personalidade e memórias vão no início do primeiro turno do usuário.
- **Tela cheia:** `SHQueryUserNotificationState` (via `ctypes`) — esconder quando for `QUNS_BUSY`, `QUNS_RUNNING_D3D_FULL_SCREEN` ou `QUNS_PRESENTATION_MODE`.
- **Ocioso (cochilo):** `GetLastInputInfo` via `ctypes`.
- **Instalação:** PyInstaller `--onedir` + instalador **Inno Setup**, por usuário (sem admin) em `%LOCALAPPDATA%\Mascote\`. Dados em `%LOCALAPPDATA%\Mascote\dados\` (sobrevivem a reinstalação). Opção no instalador: "iniciar com o Windows" (atalho na pasta Inicializar), marcada por padrão.
- **Lembretes não saem do app:** sem Agendador de Tarefas nem notificação do Windows; o pet precisa estar aberto pra avisar e recupera os atrasados ao abrir.
- **Tamanho final:** ~6 GB instalados, dominado pelo modelo. `.exe` único foi descartado (descompactaria 5 GB a cada abertura).

## Deixado para quem construir

- Nome do pet (usar "Mascote" como provisório) e ícone.
- Paleta exata, tamanho, curvas de animação, frequência de piscar.
- Como a extração de memórias acontece (automática após cada conversa, ou só quando o Samuel diz algo "sobre si") — desde que dê pra listar e apagar.
- Menu de botão direito (sugestão: mudar horário do almoço, ver lembretes, sair).
- Versão do Python no build caso PySide6/PyInstaller ainda não suportem 3.14 (usar 3.12/3.13 num venv é aceitável).
- Parâmetros do llama-server (contexto, `-ngl`), desde que caiba nos 8 GB da RX 580.
