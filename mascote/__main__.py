import sys

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication

from .app import App
from .config import pasta_dados


def main() -> int:
    if "--baixar-modelo" in sys.argv:  # chamado pelo instalador
        from .baixar_ui import baixar_com_janela
        from .config import preferencias

        app = QApplication(sys.argv)
        return 0 if baixar_com_janela(preferencias()["Nome"]) else 1
    trava = QLockFile(str(pasta_dados() / "mascote.lock"))
    if not trava.tryLock(100):
        return 0  # já tem um Mascote rodando
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    mascote = App()
    mascote.iniciar()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
