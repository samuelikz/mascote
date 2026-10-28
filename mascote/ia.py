import ctypes
import json
import os
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .config import RECURSOS, pasta_dados


class ErroIA(Exception):
    pass


class _BASICO(ctypes.Structure):  # JOBOBJECT_BASIC_LIMIT_INFORMATION
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32), ("SchedulingClass", ctypes.c_uint32),
    ]


class _LIMITES(ctypes.Structure):  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    _fields_ = [("BasicLimitInformation", _BASICO), ("IoInfo", ctypes.c_uint64 * 6), ("memoria", ctypes.c_size_t * 4)]


def _job_que_mata_ao_fechar():
    """Job do Windows: quando o pet morre (até por Gerenciador de Tarefas), o llama-server morre junto."""
    k32 = ctypes.windll.kernel32
    k32.CreateJobObjectW.restype = ctypes.c_void_p
    job = k32.CreateJobObjectW(None, None)
    info = _LIMITES()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not job or not k32.SetInformationJobObject(ctypes.c_void_p(job), 9, ctypes.byref(info), ctypes.sizeof(info)):
        return None
    return job


_JOB = _job_que_mata_ao_fechar()


class ServidorIA:
    """llama-server rodando como subprocesso, ligado sob demanda e desligado quando ocioso."""

    def __init__(self, exe: Path, modelo: Path, ocioso_s: int = 300, timeout_s: int = 60):
        self.exe, self.modelo = Path(exe), Path(modelo)
        self.ocioso_s, self.timeout_s = ocioso_s, timeout_s
        self.proc: subprocess.Popen | None = None
        self.porta = 0
        self.ultimo_uso = 0.0
        self.senha = ""
        self.log = None
        self.trava = threading.Lock()

    @classmethod
    def padrao(cls, **kw) -> "ServidorIA":
        return cls(RECURSOS / "llama" / "llama-server.exe", RECURSOS / "modelo" / "gemma2-9b.gguf", **kw)

    def disponivel(self) -> bool:
        return self.exe.is_file() and self.modelo.is_file()

    @property
    def ligado(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _url(self, caminho: str) -> str:
        return f"http://127.0.0.1:{self.porta}{caminho}"

    def _pedido(self, caminho: str, corpo: bytes | None = None) -> urllib.request.Request:
        return urllib.request.Request(
            self._url(caminho), corpo, {"Content-Type": "application/json", "Authorization": f"Bearer {self.senha}"})

    def garantir_ligado(self) -> None:
        if self.ligado:
            return
        if not self.disponivel():
            raise ErroIA(f"faltando {self.exe if not self.exe.is_file() else self.modelo}")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.porta = s.getsockname()[1]
        self.senha = secrets.token_urlsafe(24)  # só este processo conversa com o servidor
        if self.log is not None:
            self.log.close()
        self.log = open(pasta_dados() / "llama.log", "wb")
        self.proc = subprocess.Popen(
            [str(self.exe), "-m", str(self.modelo), "--host", "127.0.0.1", "--port", str(self.porta), "-ngl", "99", "-c", "4096"],
            env={**os.environ, "LLAMA_API_KEY": self.senha},  # fora da linha de comando, que outros processos leem
            stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,  # stdin explícito: exe sem console não tem um
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if _JOB:
            ctypes.windll.kernel32.AssignProcessToJobObject(ctypes.c_void_p(_JOB), ctypes.c_void_p(int(self.proc._handle)))
        limite = time.time() + self.timeout_s
        while time.time() < limite:
            if self.proc.poll() is not None:
                self.proc = None
                raise ErroIA("o servidor de IA fechou sozinho")
            try:
                # /v1/models exige a senha: só responde 200 se for o nosso servidor e o modelo já carregou
                with urllib.request.urlopen(self._pedido("/v1/models"), timeout=2) as r:
                    if r.status == 200 and self.ligado:
                        self.ultimo_uso = time.time()
                        return
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.25)
        self.desligar()
        raise ErroIA("o servidor de IA demorou demais pra ligar")

    def perguntar(self, mensagens: list[dict], max_tokens: int = 512, temperatura: float = 0.7) -> str:
        with self.trava:
            self.garantir_ligado()
            corpo = json.dumps({"messages": mensagens, "max_tokens": max_tokens, "temperature": temperatura}).encode()
            try:
                with urllib.request.urlopen(self._pedido("/v1/chat/completions", corpo), timeout=180) as r:
                    resposta = json.load(r)["choices"][0]["message"]["content"]
            except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as e:
                raise ErroIA(f"falha ao perguntar: {e}") from e
            finally:
                self.ultimo_uso = time.time()
            return resposta

    def desligar_se_ocioso(self, agora: float) -> None:
        if self.ligado and not self.trava.locked() and agora - self.ultimo_uso >= self.ocioso_s:
            self.desligar()

    def desligar(self) -> None:
        if self.proc is not None:
            self.proc.kill()
            self.proc.wait()
            self.proc = None
            self.senha, self.porta = "", 0


class PonteIA(QObject):
    """Roda perguntas numa thread e devolve o resultado na thread da interface."""

    pronto = Signal(str, object)
    falhou = Signal(str, object)

    def __init__(self, servidor: ServidorIA):
        super().__init__()
        self.servidor = servidor

    def pedir(self, mensagens: list[dict], etiqueta: object, max_tokens: int = 512, temperatura: float = 0.7) -> None:
        def trabalho():
            try:
                self.pronto.emit(self.servidor.perguntar(mensagens, max_tokens, temperatura), etiqueta)
            except ErroIA as e:
                self.falhou.emit(str(e), etiqueta)

        threading.Thread(target=trabalho, daemon=True).start()
