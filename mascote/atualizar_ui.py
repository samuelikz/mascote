"""Janela de progresso do download da atualização."""
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from . import atualizar

MB = 1024 * 1024


class _Ponte(QObject):
    andou = Signal(int, int)
    acabou = Signal(object)  # Path ou mensagem de erro (str)


def atualizar_com_janela(nome: str, atu: atualizar.Atualizacao) -> bool:
    janela = QProgressDialog(f"Baixando o {nome} {atu.versao}…", "Cancelar", 0, 1000)
    janela.setWindowTitle(nome)
    janela.setWindowModality(Qt.ApplicationModal)
    janela.setMinimumWidth(380)
    janela.setMinimumDuration(0)
    janela.setAutoClose(False)
    janela.setAutoReset(False)
    ponte, resultado, cancelar = _Ponte(), {}, threading.Event()

    def andou(feito: int, total: int) -> None:
        janela.setValue(feito * 1000 // max(total, 1))
        janela.setLabelText(f"Baixando o {nome} {atu.versao}… {feito / MB:.1f} de {total / MB:.1f} MB".replace(".", ","))

    def acabou(r) -> None:
        resultado["r"] = r
        janela.close()

    ponte.andou.connect(andou)
    ponte.acabou.connect(acabou)
    janela.canceled.connect(cancelar.set)

    def trabalho():
        try:
            ponte.acabou.emit(atualizar.baixar(atu, ponte.andou.emit, cancelar.is_set))
        except Exception as e:
            ponte.acabou.emit(str(e) or "falhou")

    threading.Thread(target=trabalho, daemon=True).start()
    janela.exec()
    while "r" not in resultado:
        cancelar.set()
        QApplication.processEvents()
        threading.Event().wait(0.05)
    r = resultado["r"]
    if isinstance(r, str):
        if not cancelar.is_set():
            QMessageBox.warning(None, nome, f"Não consegui baixar a atualização ({r}).")
        return False
    try:
        atualizar.instalar(r)
    except OSError as e:  # recusou o administrador
        QMessageBox.information(None, nome, f"A atualização não foi instalada ({e.strerror or e}).")
        return False
    return True
