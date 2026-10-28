import random
import re
import threading
import time
from datetime import datetime, timedelta

from PySide6.QtCore import QFileSystemWatcher, QLocale, QObject, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QInputDialog, QMenu, QSystemTrayIcon

from . import atualizar, claude, config, memoria
from .agenda import Agenda, Lembrete, proximo_disparo
from .balao import Balao
from .baixar import ia_instalada
from .ia import ClienteOllama, PonteIA, criar_ia
from .janelas import ATALHO, administrador, segundos_ocioso, tela_cheia
from .pet import ACESSORIOS, CORES, Pet
from .prompts import (
    ESQUEMA_LEMBRETE, LIMITE, conferir_extracao, ler_extracao, mensagens_chat, mensagens_extrair, mensagens_melhorar,
    mensagens_resumir, mensagens_traduzir, parece_portugues, separar_memoria,
)

DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
FOME_HORAS = 4
COCHILO_S = 600
PAUSA_S = 90 * 60  # tempo de uso sem parar até sugerir uma pausa
PARADA_S = 300  # ociosidade que conta como pausa feita
LIMITE_MEMORIA = 500  # caracteres por item guardado; o chat leva as memórias em todo pedido
OPCOES = {  # liga/desliga do menu Ajustes: chave no config.json, rótulo
    "iniciativa": "Puxar conversa sozinho 💬",
    "voz": "Falar em voz alta 🔊",
    "area_transferencia": "Oferecer tradução do que eu copiar 📋",
}


FALAS = {  # várias versões de cada frase, pra ele não soar repetido
    "nhac": ["Nhac! 😋 o que eu faço com isso?", "hmm, gostoso! 😋 e agora?", "nham nham 😋 o que eu faço com isso?",
             "chegou comida! 🍽️ o que eu faço?"],
    "feito": ["eba! ✅", "boa! 🎉", "isso aí! ✅", "mandou bem! 💪"],
    "guardei": ["guardei! 🧠", "anotado na cabecinha 🧠", "pode deixar, não esqueço 🧠"],
    "adiar": ["tá bom, te chamo em 10 min ⏰", "beleza, daqui 10 min eu volto ⏰", "ok! mais 10 minutinhos ⏰"],
    "lembrar": ["Nhac! 😋 vou te lembrar", "anotado! 📌 vou te lembrar", "pode deixar! 📌 te lembro"],
    "carinho": ["hihi 🥰", "que gostoso 💕", "mais! mais! 🥰", "ronron… 💕"],
}


def fala(chave: str) -> str:
    return random.choice(FALAS[chave])


def ofertas(texto: str) -> list[str]:
    """O que oferecer pro texto copiado: traduzir (frase em outra língua) e/ou resumir (textão). Código e link, nada."""
    if not 20 <= len(texto) <= LIMITE or len(re.findall(r"[{};=<>]", texto)) > len(texto) / 100:
        return []
    palavras = len(re.findall(r"[A-Za-zÀ-ú]{2,}", texto))
    acoes = []
    if palavras >= 4 and "://" not in texto and not parece_portugues(texto):
        acoes.append("traduzir")
    if palavras >= 80:
        acoes.append("resumir")
    return acoes


def escolher_fala_lembrete(l: Lembrete) -> str:
    return "ei, bora comer? 🍔" if l.texto == "ALMOCO" else f"ei! hora de {l.texto} 💡"


def _hora(d: datetime) -> str:
    return f"{d.hour}h" if d.minute == 0 else f"{d.hour}h{d.minute:02d}"


def descrever_quando(quando: datetime, regra: dict | None, agora: datetime) -> str:
    h = _hora(quando)
    if regra is None:
        dias = (quando.date() - agora.date()).days
        if dias == 0:
            return f"hoje às {h}"
        if dias == 1:
            return f"amanhã às {h}"
        if 1 < dias < 7:
            return f"{DIAS[quando.weekday()]} às {h}"
        return f"{quando:%d/%m} às {h}"
    if regra["tipo"] == "diario":
        return f"todo dia às {h}"
    if regra["tipo"] == "mensal":
        return f"todo dia {regra['dia']} às {h}"
    dias = regra["dias"]
    if dias == [0, 1, 2, 3, 4]:
        return f"de segunda a sexta às {h}"
    if len(dias) == 1:
        return f"{'todo' if dias[0] >= 5 else 'toda'} {DIAS[dias[0]]} às {h}"
    curtos = [DIAS[d][:3] for d in dias]
    return f"toda {', '.join(curtos[:-1])} e {curtos[-1]} às {h}"


def parametros(tipo: str) -> tuple[float, int]:
    """(temperatura, max_tokens): JSON e texto pronto pedem resposta firme; texto pronto precisa de espaço."""
    return {"lembrar": (0.1, 256), "resultado": (0.3, 4096)}.get(tipo, (0.7, 512))


def saudacao(agora: datetime, hoje: list[str]) -> str:
    oi = "bom dia! ☀️" if agora.hour < 12 else "boa tarde! 🌤️" if agora.hour < 18 else "boa noite! 🌙"
    return f"{oi} hoje tem: {', '.join(hoje)}" if hoje else f"{oi} nada marcado pra hoje, dia livre 😄"



def sem_emoji(texto: str) -> str:
    return re.sub(r"[^\w\s.,!?;:'\"()\-–—…%/]", "", texto).strip()


def ajustar_quando(quando: datetime, regra: dict | None, agora: datetime) -> datetime | None:
    """Com repetição, a regra manda (só a hora de `quando` vale). Sem repetição, horário no passado = perguntar de novo."""
    if regra:
        return proximo_disparo(quando, regra, agora - timedelta(minutes=1))
    return quando if quando > agora - timedelta(minutes=1) else None


class App(QObject):
    achou_atualizacao = Signal(object, bool)  # (Atualizacao | None | str de erro, foi pedido no menu)

    def __init__(self):
        super().__init__()
        self.cfg = config.carregar()
        if not self.cfg["ultima_comida"]:
            self.cfg["ultima_comida"] = datetime.now().isoformat()
            config.salvar(self.cfg)
        self.agenda = Agenda(config.pasta_dados() / "agenda.db")
        self.prefs = config.preferencias()  # nome e IA escolhidos no instalador
        self.servidor = criar_ia(self.prefs)
        self.ia = PonteIA(self.servidor)
        self.pet = Pet(self.cfg["canto"], self.cfg["cor"], self.cfg["acessorio"])
        self.balao = Balao()
        self.escondido = False  # o usuário mandou esconder (volta pela bandeja)
        self.fantasma = False
        self.ativo_desde = time.time()
        self.voz = None  # QTextToSpeech, criado na primeira fala
        self.bandeja = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.bandeja = QSystemTrayIcon(QIcon(self.pet.grab()), self)
            self.bandeja.setToolTip(self.prefs["Nome"])
            self.bandeja.activated.connect(self.clicou_bandeja)
        self.vigia = QFileSystemWatcher(self)
        self.vigia.fileChanged.connect(self.evento_claude)
        self.historico: list[dict] = []
        self.comida = ""
        self.esperando_quando = ""  # texto de um lembrete que ainda não tem horário
        self.lembrete_na_tela: int | None = None
        self.pendentes = 0  # pedidos na fila da IA: fica "pensando" até o último voltar
        self.relogio = QTimer(self, interval=20_000, timeout=self.checar)

        self.ia.pronto.connect(self.ia_respondeu)
        self.ia.falhou.connect(self.ia_falhou)
        self.ia.pedaco.connect(self.ia_escrevendo)
        QGuiApplication.clipboard().dataChanged.connect(self.copiou)
        self.pet.clicado.connect(self.abrir_chat)
        self.pet.clique_direito.connect(self.menu)
        self.pet.comeu.connect(self.comeu)
        self.pet.mudou_canto.connect(self.mudou_canto)
        self.pet.carinho.connect(self.ganhou_carinho)
        self.pet.atalho.connect(self.atalho_comida)
        self.ultimo_carinho = 0.0
        self.balao.escolheu.connect(self.escolheu)
        self.balao.enviou.connect(self.enviou)
        self.balao.apagar.connect(self.apagar)
        self.balao.fechou.connect(self.balao_fechou)
        self.achou_atualizacao.connect(self.mostrar_atualizacao)
        QApplication.instance().aboutToQuit.connect(lambda: self.servidor.desligar())

    def iniciar(self) -> None:
        self.agenda.garantir_almoco(self.cfg["almoco"])
        self.pet.show()
        if self.bandeja:
            self.bandeja.show()
        arquivo = claude.arquivo_evento()
        if not arquivo.exists():
            arquivo.write_text("", encoding="utf-8")
        self.vigia.addPath(str(arquivo))
        self.posicionar_balao()
        self.relogio.start()
        QTimer.singleShot(1500, self.checar)
        QTimer.singleShot(60_000, lambda: self.verificar_atualizacao(pedido=False))  # confere sozinho ao abrir
        if administrador():
            QTimer.singleShot(3000, lambda: self.dizer(
                "tô rodando como administrador 😬 assim o Windows não me deixa receber texto arrastado. "
                "me fecha e abre de novo pelo menu Iniciar?", ms=20000))

    # ---- fala ----
    def posicionar_balao(self) -> None:
        self.pet.parar_passeio()  # o balão gruda no canto: o pet volta pra lá antes
        self.balao.posicionar(self.pet.frameGeometry(), self.pet.canto)

    def livre(self) -> bool:
        """Nada na tela esperando o usuário: dá pra puxar assunto ou passear."""
        return self.pet.isVisible() and not self.balao.isVisible() and self.lembrete_na_tela is None

    def falar_alto(self, texto: str) -> None:
        if not self.cfg["voz"] or not sem_emoji(texto):
            return
        if self.voz is None:
            from PySide6.QtTextToSpeech import QTextToSpeech

            self.voz = QTextToSpeech(self)
            pt = [l for l in self.voz.availableLocales() if l.language() == QLocale.Portuguese]
            if pt:
                self.voz.setLocale(next((l for l in pt if l.territory() == QLocale.Brazil), pt[0]))
        self.voz.say(sem_emoji(texto))

    def dizer(self, texto: str, botoes: list | None = None, ms: int | None = 6000) -> None:
        self.falar_alto(texto)
        if self.balao.modo == "chat" and self.balao.isVisible() and not botoes:
            self.balao.acrescentar_chat("assistant", texto)
            return
        self.posicionar_balao()
        self.balao.falar(texto, botoes or [], ms)

    def pedir(self, mensagens: list[dict], etiqueta: tuple) -> None:
        self.pendentes += 1
        self.pet.definir_estado("pensando")
        temperatura, max_tokens = parametros(etiqueta[0])
        extra = {"esquema": ESQUEMA_LEMBRETE} if etiqueta[0] == "lembrar" else {"fluxo": True} if etiqueta[0] == "chat" else {}
        self.ia.pedir(mensagens, etiqueta, max_tokens=max_tokens, temperatura=temperatura, **extra)

    def _terminou_pedido(self) -> None:
        self.pendentes = max(0, self.pendentes - 1)
        if self.pendentes:
            self.pet.definir_estado("pensando")
        else:
            self.pet.voltar()

    def _mostrar_lembrete(self, id: int | None) -> None:
        """Lembrete na tela deixa o pet chamando até ser respondido, mesmo depois de outras caretas."""
        self.lembrete_na_tela = id
        self.pet.base = "parado" if id is None else "chamando"
        if self.pet.estado in ("parado", "chamando"):
            self.pet.voltar()

    def balao_fechou(self) -> None:
        self.esperando_quando = ""  # fechou o chat: desistiu do "pra quando?"

    # ---- relógio ----
    def checar(self) -> None:
        agora = datetime.now()
        self.servidor.desligar_se_ocioso(time.time())
        if tela_cheia() or self.escondido:
            self.pet.hide()
            self.balao.hide()
            return
        if not self.pet.isVisible():
            self.pet.show()
        if self.lembrete_na_tela is not None and not (self.balao.isVisible() and self.balao.modo == "lembrete"):
            # algo tampou o balão (comida, menu, tela cheia): o lembrete continua vencido e volta agora
            self._mostrar_lembrete(None)
        if self.lembrete_na_tela is None:
            vencidos = self.agenda.vencidos(agora)
            if vencidos:
                l = vencidos[0]
                self._mostrar_lembrete(l.id)
                self.pet.definir_estado("chamando")
                self.posicionar_balao()
                self.falar_alto(escolher_fala_lembrete(l))
                self.balao.falar(escolher_fala_lembrete(l), [("feito ✅", ("feito", l.id)), ("depois ⏰", ("adiar", l.id))],
                                 None, modo="lembrete")
                return
        ocioso = segundos_ocioso()
        if self.pet.estado in ("parado", "fome", "cochilo") and self.lembrete_na_tela is None:
            faminto = agora - datetime.fromisoformat(self.cfg["ultima_comida"]) > timedelta(hours=FOME_HORAS)
            novo = "cochilo" if ocioso > COCHILO_S else "fome" if faminto else "parado"
            if novo != self.pet.estado:
                self.pet.definir_estado(novo)
        if ocioso > PARADA_S:
            self.ativo_desde = time.time()
        if self.cfg["iniciativa"] and self.livre():
            self.puxar_assunto(agora)
        if self.livre() and self.pet.estado == "parado" and random.random() < 0.12:
            self.pet.passear()  # de vez em quando dá uma voltinha pela borda (~a cada 3 min)

    def puxar_assunto(self, agora: datetime) -> None:
        if self.cfg["bom_dia"] != agora.date().isoformat():
            self.cfg["bom_dia"] = agora.date().isoformat()
            config.salvar(self.cfg)
            hoje = [("almoço" if l.texto == "ALMOCO" else l.texto) + f" às {_hora(l.proximo)}"
                    for l in self.agenda.listar() if l.proximo.date() == agora.date() and l.proximo > agora]
            self.pet.definir_estado("feliz", 2000)
            self.dizer(saudacao(agora, hoje), ms=10000)
        elif time.time() - self.ativo_desde > PAUSA_S:
            self.ativo_desde = time.time()
            self.pet.definir_estado("chamando", 2000)
            self.dizer("já faz 1h30 que você tá aí direto… bora uma pausa? 🧘 água, alongar, olhar longe 👀", ms=10000)

    # ---- área de transferência ----
    def copiou(self) -> None:
        texto = QGuiApplication.clipboard().text().strip()
        if not self.cfg["area_transferencia"] or texto == self.balao.copiado or not self.livre():
            return
        acoes = ofertas(texto)
        if not acoes:
            return
        self.comida = texto
        pergunta = {("traduzir",): "copiou um texto em outra língua 👀 quer que eu traduza?",
                    ("resumir",): "copiou um textão 📄 quer que eu resuma?",
                    ("traduzir", "resumir"): "copiou um textão em outra língua 👀 traduzo ou resumo?"}[tuple(acoes)]
        botoes = {"traduzir": ("traduzir 🌎", ("comida", "traduzir")), "resumir": ("resumir 📝", ("comida", "resumir"))}
        self.dizer(pergunta, [botoes[a] for a in acoes] + [("agora não", ("nada", None))])
        self.balao.sumir.start(10000)  # pergunta com botão, mas não fica pra sempre

    def atalho_comida(self) -> None:
        texto = QGuiApplication.clipboard().text().strip()
        self.escondido = False
        if not self.pet.isVisible() and not tela_cheia():
            self.pet.show()
        if texto:
            self.comeu(texto)
        else:
            self.pet.definir_estado("triste", 2000)
            self.dizer(f"copia um texto e aperta {ATALHO} que eu como 😋", ms=4000)

    def ganhou_carinho(self) -> None:
        if not self.balao.isVisible() and time.time() - self.ultimo_carinho > 20:
            self.ultimo_carinho = time.time()
            self.dizer(fala("carinho"), ms=2500)

    # ---- Claude Code ----
    def evento_claude(self, caminho: str) -> None:
        if caminho not in self.vigia.files():
            self.vigia.addPath(caminho)  # alguns jeitos de gravar trocam o arquivo e o vigia solta
        try:
            evento = claude.arquivo_evento().read_text(encoding="utf-8").strip()
        except OSError:
            return
        if not self.pet.isVisible() or self.lembrete_na_tela is not None:
            return
        if evento == "pensando" and not self.pendentes:
            self.pet.definir_estado("pensando", 10 * 60_000)  # se o Claude nunca avisar que acabou, volta sozinho
        elif evento == "pronto":
            self.pet.definir_estado("feliz", 2000)
            if not self.balao.isVisible():
                self.dizer("o Claude terminou! ✅", ms=4000)
        elif evento == "chamando":
            self.pet.definir_estado("chamando", 3000)
            if not self.balao.isVisible():
                self.dizer("o Claude Code precisa de você 👀", ms=6000)

    # ---- comida ----
    def comeu(self, texto: str) -> None:
        self.comida = texto
        self.cfg["ultima_comida"] = datetime.now().isoformat()
        config.salvar(self.cfg)
        self.pet.definir_estado("feliz", 1500)
        self.dizer(fala("nhac"), [
            ("lembrar 📌", ("comida", "lembrar")), ("guardar 🧠", ("comida", "guardar")),
            ("melhorar ✨", ("comida", "melhorar")), ("traduzir 🌎", ("comida", "traduzir")),
            ("resumir 📝", ("comida", "resumir")), ("engolir 😋", ("comida", "engolir")),
        ])

    def escolheu(self, valor: tuple) -> None:
        tipo, dado = valor
        agora = datetime.now()
        if tipo == "nada":
            self.balao.fechar()
        elif tipo == "baixar":
            from .baixar_ui import baixar_com_janela

            self.balao.fechar()
            if baixar_com_janela(self.prefs["Nome"]):
                self.pet.definir_estado("feliz", 2000)
                self.dizer("cérebro instalado! 🧠✨ agora sim, fala comigo")
        elif tipo == "atualizar":
            from .atualizar_ui import atualizar_com_janela

            self.balao.fechar()
            if atualizar_com_janela(self.prefs["Nome"], dado):
                self.dizer("instalando a atualização… já volto! 🔄", ms=None)
        elif tipo == "feito":
            self.agenda.feito(dado, agora)
            self._mostrar_lembrete(None)
            self.pet.definir_estado("feliz", 2000)
            self.dizer(fala("feito"))
        elif tipo == "adiar":
            self.agenda.adiar(dado, agora)
            self._mostrar_lembrete(None)
            self.dizer(fala("adiar"), ms=3000)
        elif dado == "lembrar":
            self.pedir(mensagens_extrair(self.comida, agora), ("lembrar", self.comida))
        elif dado == "engolir":  # só comer, sem guardar nada
            self.pet.definir_estado("feliz", 2000)
            self.dizer("engoli todo o texto! 😋")
        elif dado == "guardar":
            memoria.adicionar(self.comida.strip()[:LIMITE_MEMORIA])
            self.pet.definir_estado("feliz", 2000)
            self.dizer(fala("guardei"))
        elif dado == "melhorar":
            self.pedir(mensagens_melhorar(self.comida), ("resultado",))
        elif dado == "traduzir":
            self.pedir(mensagens_traduzir(self.comida), ("resultado",))
        elif dado == "resumir":
            self.pedir(mensagens_resumir(self.comida), ("resultado",))

    # ---- chat ----
    def abrir_chat(self) -> None:
        if self.lembrete_na_tela is not None:
            return  # primeiro responde o lembrete
        self.posicionar_balao()
        self.balao.abrir_chat(self.historico)

    def enviou(self, texto: str) -> None:
        agora = datetime.now()
        if self.esperando_quando:
            pedido, self.esperando_quando = f"{self.esperando_quando} — {texto}", ""
            self.pedir(mensagens_extrair(pedido, agora), ("lembrar", pedido))
        elif re.match(r"\s*me\s+lembr", texto, re.IGNORECASE):
            self.pedir(mensagens_extrair(texto, agora), ("lembrar", texto))
        else:
            self.historico.append({"role": "user", "content": texto})
            fatos = [m["fato"] for m in memoria.listar()]
            self.pedir(mensagens_chat(self.historico, fatos, agora, self.prefs["Nome"]), ("chat",))

    # ---- respostas da IA ----
    def ia_escrevendo(self, parcial: str, etiqueta: tuple) -> None:
        if etiqueta[0] == "chat" and self.balao.modo == "chat" and self.balao.isVisible():
            visivel = re.split(r"(?im)^\s*MEMORIA:", parcial)[0].strip()  # a linha de memória não aparece nem pela metade
            if visivel:
                self.balao.escrever_rascunho(visivel)

    def ia_respondeu(self, resposta: str, etiqueta: tuple) -> None:
        self._terminou_pedido()
        tipo = etiqueta[0]
        if tipo == "chat":
            texto, fatos = separar_memoria(resposta)
            for f in fatos:
                memoria.adicionar(f)
            self.historico.append({"role": "assistant", "content": texto})
            self.falar_alto(texto)
            if self.balao.modo == "chat" and self.balao.isVisible():
                if not self.balao.fechar_rascunho(texto):
                    self.balao.acrescentar_chat("assistant", texto)
            elif self.lembrete_na_tela is None:
                # fechou o chat enquanto eu pensava: reabre com a resposta, sem roubar o foco
                self.posicionar_balao()
                self.balao.abrir_chat(self.historico, ativar=False)
        elif tipo == "resultado":
            self.posicionar_balao()
            self.balao.mostrar_resultado(resposta.strip())
        elif tipo == "lembrar":
            self.salvar_lembrete(resposta, etiqueta[1])

    def salvar_lembrete(self, resposta: str, original: str) -> None:
        agora = datetime.now()
        lido = ler_extracao(resposta)
        if lido is None:
            self.pet.definir_estado("triste", 2500)
            self.dizer("não entendi 😅 tenta pelo chat? tipo \"me lembra de X amanhã às 9h\"")
            return
        texto, quando, regra = lido
        quando, regra = conferir_extracao(original, quando, regra)
        quando = ajustar_quando(quando, regra, agora) if quando else None
        if quando is None:
            self.esperando_quando = texto
            if not (self.balao.modo == "chat" and self.balao.isVisible()):
                # a resposta chega segundos depois do clique: abre sem roubar o foco de quem está digitando
                self.posicionar_balao()
                self.balao.abrir_chat(self.historico, ativar=False)
            self.balao.acrescentar_chat("assistant", f"\"{texto}\" pra quando? 🤔")
            return
        self.agenda.adicionar(texto, quando, regra)
        self.pet.definir_estado("feliz", 2000)
        self.dizer(f"{fala('lembrar')} {descrever_quando(quando, regra, agora)}")

    def ia_falhou(self, erro: str, etiqueta: tuple) -> None:
        print("IA falhou:", erro)
        self._terminou_pedido()
        self.pet.definir_estado("triste", 4000)
        if isinstance(self.servidor, ClienteOllama):
            self.dizer(f"não tô achando o Ollama 🦙 ele tá aberto? ({self.prefs['ModeloOllama']})")
        elif not ia_instalada():
            self.dizer("meu cérebro ainda não foi baixado 🧠 (5,4 GB)", [("baixar agora ⬇️", ("baixar", None)), ("depois", ("nada", None))])
        else:
            self.dizer("ai, minha cabecinha falhou 😵 tenta de novo?")

    # ---- menu ----
    def menu(self, pos) -> None:
        lembretes, memorias = len(self.agenda.listar()), len(memoria.listar())
        m = QMenu()
        m.addAction("Conversar 💬", self.abrir_chat)
        dica = m.addAction(f"{ATALHO}: me dá o que você copiou 😋" if self.pet.atalho_ok
                           else f"({ATALHO} está ocupado por outro programa)")
        dica.setEnabled(False)
        if self.historico:
            m.addAction("Começar conversa nova 🧹", self.conversa_nova)
        m.addSeparator()
        m.addAction(f"Ver lembretes ⏰ ({lembretes})", self.ver_lembretes)
        m.addAction(f"O que eu lembro de você 🧠 ({memorias})", self.ver_memorias)
        m.addSeparator()
        ajustes = m.addMenu("Ajustes ⚙️")
        ajustes.addAction(f"Horário do almoço ({self.cfg['almoco']})…", self.mudar_almoco)
        ajustes.addAction(f"Meu nome ({self.prefs['Nome']})…", self.mudar_nome)
        ajustes.addAction("Modelo da IA…", self.escolher_ia)
        visual = ajustes.addMenu("Aparência 🎨")
        for cor in CORES:
            a = visual.addAction(f"cor {cor}", lambda c=cor: self.vestir(cor=c))
            a.setCheckable(True)
            a.setChecked(cor == self.cfg["cor"])
        visual.addSeparator()
        for item in ACESSORIOS:
            a = visual.addAction(item, lambda i=item: self.vestir(acessorio=i))
            a.setCheckable(True)
            a.setChecked(item == self.cfg["acessorio"])
        ajustes.addSeparator()
        for chave, rotulo in OPCOES.items():
            a = ajustes.addAction(rotulo, lambda c=chave: self.alternar(c))
            a.setCheckable(True)
            a.setChecked(bool(self.cfg[chave]))
        a = ajustes.addAction("Integração com o Claude Code 🤖", self.alternar_claude)
        a.setCheckable(True)
        a.setChecked(claude.ligado())
        m.addAction(f"Verificar atualizações (v{atualizar.VERSAO})", self.verificar_atualizacao)
        m.addSeparator()
        if self.bandeja:
            m.addAction("Aparecer 👀" if self.escondido else "Esconder 🙈 (volta pela bandeja)", self.alternar_escondido)
            a = m.addAction("Modo fantasma 👻 (clique atravessa; desliga pela bandeja)", self.alternar_fantasma)
            a.setCheckable(True)
            a.setChecked(self.fantasma)
        m.addAction("Sair 👋", QApplication.quit)
        m.exec(pos)

    # ---- bandeja e ajustes ----
    def clicou_bandeja(self, motivo) -> None:
        if motivo == QSystemTrayIcon.Context:
            self.menu(QCursor.pos())
        elif motivo == QSystemTrayIcon.Trigger:
            self.alternar_escondido()

    def alternar_escondido(self) -> None:
        self.escondido = not self.escondido
        if not self.escondido:
            self.pet.definir_estado("feliz", 1500)
        self.checar()

    def alternar_fantasma(self) -> None:
        self.fantasma = not self.fantasma
        self.pet.fantasma(self.fantasma)

    def alternar(self, chave: str) -> None:
        self.cfg[chave] = not self.cfg[chave]
        config.salvar(self.cfg)
        self.dizer(f"{OPCOES[chave].rstrip(' 💬🔊📋')}: {'ligado ✅' if self.cfg[chave] else 'desligado'}", ms=3000)

    def alternar_claude(self) -> None:
        querer = not claude.ligado()
        try:
            claude.ligar(querer)
        except (OSError, ValueError) as e:
            self.pet.definir_estado("triste", 3000)
            self.dizer(f"não consegui mexer na config do Claude Code 😕 ({e})")
            return
        self.dizer("pronto! quando o Claude Code trabalhar eu aviso 🤖 (vale nas próximas sessões dele)" if querer
                   else "desliguei a integração com o Claude Code", ms=5000)

    def vestir(self, cor: str | None = None, acessorio: str | None = None) -> None:
        self.cfg["cor"] = cor or self.cfg["cor"]
        self.cfg["acessorio"] = acessorio or self.cfg["acessorio"]
        config.salvar(self.cfg)
        self.pet.vestir(self.cfg["cor"], self.cfg["acessorio"])
        self.pet.definir_estado("feliz", 1500)
        if self.bandeja:
            self.bandeja.setIcon(QIcon(self.pet.grab()))

    def conversa_nova(self) -> None:
        self.historico.clear()
        self.esperando_quando = ""
        self.pet.definir_estado("feliz", 1500)
        if self.balao.modo == "chat" and self.balao.isVisible():
            self.abrir_chat()
        else:
            self.dizer("pronto, esqueci a conversa! 🧹 (as memórias continuam)", ms=3000)

    def ver_lembretes(self) -> None:
        agora = datetime.now()
        itens = [
            (("lembrete", l.id), "almoço 🍔 — " + descrever_quando(l.original, l.regra, agora) if l.texto == "ALMOCO"
             else f"{l.texto} — {descrever_quando(l.proximo if not l.regra else l.original, l.regra, agora)}")
            for l in self.agenda.listar()
        ]
        self.posicionar_balao()
        self.balao.mostrar_lista("Lembretes ⏰", itens)

    def ver_memorias(self) -> None:
        self.posicionar_balao()
        self.balao.mostrar_lista("O que eu lembro de você 🧠", [(("memoria", m["id"]), m["fato"]) for m in memoria.listar()])

    def apagar(self, chave: tuple) -> None:
        tipo, id = chave
        if tipo == "memoria":
            memoria.apagar(id)
        elif any(l.id == id and l.texto == "ALMOCO" for l in self.agenda.listar()):
            self.pet.definir_estado("chamando", 1500)
            QTimer.singleShot(50, self.ver_lembretes)  # almoço não se apaga: volta pra lista (dá pra mudar o horário no menu)
        else:
            self.agenda.apagar(id)

    def mudar_almoco(self) -> None:
        hora, ok = QInputDialog.getText(None, "Mascote", "Horário do almoço (HH:MM):", text=self.cfg["almoco"])
        if ok and re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", hora.strip()):
            self.cfg["almoco"] = hora.strip()
            config.salvar(self.cfg)
            self.agenda.garantir_almoco(self.cfg["almoco"])
            self.dizer(f"anotado! almoço às {hora.strip()} 🍔")

    def mudar_nome(self) -> None:
        nome, ok = QInputDialog.getText(None, self.prefs["Nome"], "Como eu me chamo?", text=self.prefs["Nome"])
        if ok and nome.strip():
            self.prefs["Nome"] = nome.strip()[:40]
            config.salvar_preferencia("Nome", self.prefs["Nome"])
            self.dizer(f"agora eu sou o {self.prefs['Nome']}! 😄")

    def escolher_ia(self) -> None:
        embutida = "IA embutida (Gemma 2 9B)"
        try:
            do_ollama = [f"Ollama: {m}" for m in ClienteOllama(self.prefs["ModeloOllama"]).modelos()]
        except Exception:
            do_ollama = []
        opcoes = [embutida] + do_ollama
        atual = embutida if self.prefs["IA"] == "embutida" else f"Ollama: {self.prefs['ModeloOllama']}"
        escolha, ok = QInputDialog.getItem(None, self.prefs["Nome"], "Qual cérebro eu uso?" + (
            "" if do_ollama else "\n(não achei o Ollama aberto)"), opcoes, opcoes.index(atual) if atual in opcoes else 0, False)
        if not ok:
            return
        if escolha == embutida:
            self.prefs["IA"] = "embutida"
        else:
            self.prefs["IA"], self.prefs["ModeloOllama"] = "ollama", escolha.removeprefix("Ollama: ")
            config.salvar_preferencia("ModeloOllama", self.prefs["ModeloOllama"])
        config.salvar_preferencia("IA", self.prefs["IA"])
        self.servidor.desligar()
        self.servidor = self.ia.servidor = criar_ia(self.prefs)
        self.dizer("pronto, troquei de cérebro! 🧠")

    # ---- atualizações ----
    def verificar_atualizacao(self, pedido: bool = True) -> None:
        if pedido:
            self.dizer("vou dar uma olhada se tem versão nova… 🔎", ms=4000)

        def trabalho():
            try:
                r = atualizar.verificar()
            except Exception as e:
                r = str(e) or "sem conexão"
            self.achou_atualizacao.emit(r, pedido)

        threading.Thread(target=trabalho, daemon=True).start()

    def mostrar_atualizacao(self, r, pedido: bool) -> None:
        if isinstance(r, atualizar.Atualizacao):
            if not pedido and self.cfg.get("ignorar_versao") == r.versao:
                return
            self.dizer(f"saiu a versão {r.versao} do {self.prefs['Nome']}! 🎉 quer atualizar agora?",
                       [("atualizar ⬇️", ("atualizar", r)), ("agora não", ("nada", None))], ms=None)
            self.cfg["ignorar_versao"] = r.versao  # sozinho, só avisa uma vez por versão
            config.salvar(self.cfg)
        elif pedido and r is None:
            self.dizer(f"já estou na versão mais nova (v{atualizar.VERSAO}) ✅")
        elif pedido:
            self.dizer(f"não consegui ver as atualizações agora 😕 ({r})")

    def mudou_canto(self, canto: str) -> None:
        self.cfg["canto"] = canto
        config.salvar(self.cfg)
        self.balao.posicionar(self.pet.frameGeometry(), canto)
