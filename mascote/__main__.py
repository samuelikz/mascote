import sys

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication

from .app import App
from .config import pasta_dados


def main() -> int:
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
