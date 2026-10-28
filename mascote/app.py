import re
import time
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QInputDialog, QMenu

from . import config, memoria
from .agenda import Agenda, Lembrete, proximo_disparo
from .balao import Balao
from .ia import PonteIA, ServidorIA
from .janelas import segundos_ocioso, tela_cheia
from .pet import Pet
from .prompts import (
    ler_extracao, mensagens_chat, mensagens_extrair, mensagens_melhorar, mensagens_traduzir, separar_memoria, truncar,
)

DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
FOME_HORAS = 4
COCHILO_S = 600


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


def ajustar_quando(quando: datetime, regra: dict | None, agora: datetime) -> datetime | None:
    """Horário no passado: com repetição vai pra próxima vez; sem repetição, melhor perguntar de novo."""
    if quando > agora - timedelta(minutes=1):
        return quando
    return proximo_disparo(quando, regra, agora) if regra else None


class App(QObject):
    def __init__(self):
        super().__init__()
        self.cfg = config.carregar()
        if not self.cfg["ultima_comida"]:
            self.cfg["ultima_comida"] = datetime.now().isoformat()
            config.salvar(self.cfg)
        self.agenda = Agenda(config.pasta_dados() / "agenda.db")
        self.servidor = ServidorIA.padrao()
        self.ia = PonteIA(self.servidor)
        self.pet = Pet(self.cfg["canto"])
        self.balao = Balao()
        self.historico: list[dict] = []
        self.comida = ""
        self.esperando_quando = ""  # texto de um lembrete que ainda não tem horário
        self.lembrete_na_tela: int | None = None
        self.relogio = QTimer(self, interval=20_000, timeout=self.checar)

        self.ia.pronto.connect(self.ia_respondeu)
        self.ia.falhou.connect(self.ia_falhou)
        self.pet.clicado.connect(self.abrir_chat)
        self.pet.clique_direito.connect(self.menu)
        self.pet.comeu.connect(self.comeu)
        self.pet.mudou_canto.connect(self.mudou_canto)
        self.balao.escolheu.connect(self.escolheu)
        self.balao.enviou.connect(self.enviou)
        self.balao.apagar.connect(self.apagar)
        QApplication.instance().aboutToQuit.connect(self.servidor.desligar)

    def iniciar(self) -> None:
        self.agenda.garantir_almoco(self.cfg["almoco"])
        self.pet.show()
        self.balao.posicionar(self.pet.frameGeometry(), self.pet.canto)
        self.relogio.start()
        QTimer.singleShot(1500, self.checar)

    # ---- fala ----
    def dizer(self, texto: str, botoes: list | None = None, ms: int | None = 6000) -> None:
        if self.balao.modo == "chat" and self.balao.isVisible() and not botoes:
            self.balao.acrescentar_chat("assistant", texto)
            return
        self.balao.posicionar(self.pet.frameGeometry(), self.pet.canto)
        self.balao.falar(texto, botoes or [], ms)

    def pedir(self, mensagens: list[dict], etiqueta: tuple) -> None:
        self.pet.definir_estado("pensando")
        self.ia.pedir(mensagens, etiqueta)

    # ---- relógio ----
    def checar(self) -> None:
        agora = datetime.now()
        self.servidor.desligar_se_ocioso(time.time())
        if tela_cheia():
            self.pet.hide()
            self.balao.hide()
            return
        if not self.pet.isVisible():
            self.pet.show()
        if self.lembrete_na_tela is None and not (self.balao.modo == "chat" and self.balao.isVisible()):
            vencidos = self.agenda.vencidos(agora)
            if vencidos:
                l = vencidos[0]
                self.lembrete_na_tela = l.id
                self.pet.definir_estado("chamando")
                self.dizer(escolher_fala_lembrete(l), [("feito ✅", ("feito", l.id)), ("depois ⏰", ("adiar", l.id))], None)
                return
        if self.pet.estado in ("parado", "fome", "cochilo") and self.lembrete_na_tela is None:
            faminto = agora - datetime.fromisoformat(self.cfg["ultima_comida"]) > timedelta(hours=FOME_HORAS)
            novo = "cochilo" if segundos_ocioso() > COCHILO_S else "fome" if faminto else "parado"
            if novo != self.pet.estado:
                self.pet.definir_estado(novo)

    # ---- comida ----
    def comeu(self, texto: str) -> None:
        self.comida = texto
        self.cfg["ultima_comida"] = datetime.now().isoformat()
        config.salvar(self.cfg)
        self.pet.definir_estado("feliz", 1500)
        self.dizer("Nhac! 😋 o que eu faço com isso?", [
            ("lembrar 📌", ("comida", "lembrar")), ("guardar 🧠", ("comida", "guardar")),
            ("melhorar ✨", ("comida", "melhorar")), ("traduzir 🌎", ("comida", "traduzir")),
        ])

    def escolheu(self, valor: tuple) -> None:
        tipo, dado = valor
        agora = datetime.now()
        if tipo == "feito":
            self.agenda.feito(dado, agora)
            self.lembrete_na_tela = None
            self.pet.definir_estado("feliz", 2000)
            self.dizer("eba! ✅")
        elif tipo == "adiar":
            self.agenda.adiar(dado, agora)
            self.lembrete_na_tela = None
            self.pet.definir_estado("parado")
            self.dizer("tá bom, te chamo em 10 min ⏰", ms=3000)
        elif dado == "lembrar":
            self.pedir(mensagens_extrair(self.comida, agora), ("lembrar", self.comida))
        elif dado == "guardar":
            memoria.adicionar(truncar(self.comida))
            self.pet.definir_estado("feliz", 2000)
            self.dizer("guardei! 🧠")
        elif dado == "melhorar":
            self.pedir(mensagens_melhorar(self.comida), ("resultado",))
        elif dado == "traduzir":
            self.pedir(mensagens_traduzir(self.comida), ("resultado",))

    # ---- chat ----
    def abrir_chat(self) -> None:
        if self.lembrete_na_tela is not None:
            return  # primeiro responde o lembrete
        self.balao.posicionar(self.pet.frameGeometry(), self.pet.canto)
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
            self.pedir(mensagens_chat(self.historico, fatos, agora), ("chat",))

    # ---- respostas da IA ----
    def ia_respondeu(self, resposta: str, etiqueta: tuple) -> None:
        self.pet.definir_estado("parado")
        tipo = etiqueta[0]
        if tipo == "chat":
            texto, fatos = separar_memoria(resposta)
            for f in fatos:
                memoria.adicionar(f)
            self.historico.append({"role": "assistant", "content": texto})
            self.balao.acrescentar_chat("assistant", texto)
        elif tipo == "resultado":
            self.balao.posicionar(self.pet.frameGeometry(), self.pet.canto)
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
        quando = ajustar_quando(quando, regra, agora) if quando else None
        if quando is None:
            self.esperando_quando = texto
            if not (self.balao.modo == "chat" and self.balao.isVisible()):
                self.abrir_chat()
            self.balao.acrescentar_chat("assistant", f"\"{texto}\" pra quando? 🤔")
            return
        self.agenda.adicionar(texto, quando, regra)
        self.pet.definir_estado("feliz", 2000)
        self.dizer(f"Nhac! 😋 vou te lembrar {descrever_quando(quando, regra, agora)}")

    def ia_falhou(self, erro: str, etiqueta: tuple) -> None:
        print("IA falhou:", erro)
        self.pet.definir_estado("triste", 4000)
        self.dizer("ai, minha cabecinha falhou 😵 tenta de novo?")

    # ---- menu ----
    def menu(self, pos) -> None:
        m = QMenu()
        m.addAction("Ver lembretes", self.ver_lembretes)
        m.addAction("O que eu lembro de você", self.ver_memorias)
        m.addAction("Horário do almoço…", self.mudar_almoco)
        m.addSeparator()
        m.addAction("Sair", QApplication.quit)
        m.exec(pos)

    def ver_lembretes(self) -> None:
        agora = datetime.now()
        itens = [
            (("lembrete", l.id), "almoço 🍔 — " + descrever_quando(l.original, l.regra, agora) if l.texto == "ALMOCO"
             else f"{l.texto} — {descrever_quando(l.proximo if not l.regra else l.original, l.regra, agora)}")
            for l in self.agenda.listar()
        ]
        self.balao.posicionar(self.pet.frameGeometry(), self.pet.canto)
        self.balao.mostrar_lista("Lembretes ⏰", itens)

    def ver_memorias(self) -> None:
        self.balao.posicionar(self.pet.frameGeometry(), self.pet.canto)
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

    def mudou_canto(self, canto: str) -> None:
        self.cfg["canto"] = canto
        config.salvar(self.cfg)
        self.balao.posicionar(self.pet.frameGeometry(), canto)
