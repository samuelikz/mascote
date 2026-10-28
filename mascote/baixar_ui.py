"""Janelinha de progresso do download do modelo, usada pelo instalador (--baixar-modelo) e pelo pet."""
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from .baixar import ErroDownload, obter_ia

MB = 1024 * 1024


class _Ponte(QObject):
    andou = Signal(int, int)
    acabou = Signal(str)  # "" = deu certo, senão a mensagem de erro


def baixar_com_janela(nome: str) -> bool:
    janela = QProgressDialog(f"Baixando o cérebro do {nome} (Gemma 2 9B, 5,4 GB)…", "Cancelar", 0, 1000)
    janela.setWindowTitle(nome)
    janela.setWindowModality(Qt.ApplicationModal)
    janela.setMinimumWidth(420)
    janela.setMinimumDuration(0)
    janela.setAutoClose(False)
    janela.setAutoReset(False)
    ponte, resultado, cancelar = _Ponte(), {}, threading.Event()

    def andou(feito: int, total: int) -> None:
        janela.setValue(feito * 1000 // max(total, 1))
        janela.setLabelText(f"Baixando o cérebro do {nome}… {feito // MB:,} de {total // MB:,} MB".replace(",", "."))

    def acabou(erro: str) -> None:
        resultado["erro"] = erro
        janela.close()

    ponte.andou.connect(andou)
    ponte.acabou.connect(acabou)
    janela.canceled.connect(cancelar.set)

    def trabalho():
        try:
            obter_ia(ponte.andou.emit, cancelado=cancelar.is_set)
            ponte.acabou.emit("")
        except (ErroDownload, OSError) as e:
            ponte.acabou.emit(str(e) or "falhou")

    threading.Thread(target=trabalho, daemon=True).start()
    janela.exec()
    while "erro" not in resultado:  # cancelou: espera a thread soltar o arquivo
        cancelar.set()
        QApplication.processEvents()
        threading.Event().wait(0.05)
    if resultado["erro"] and not cancelar.is_set():
        QMessageBox.warning(None, nome, f"Não consegui baixar a IA agora ({resultado['erro']}).\n"
                                        f"Tudo bem: o {nome} oferece baixar de novo quando você falar com ele.")
    return not resultado["erro"]
