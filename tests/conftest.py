import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # testes não abrem janelas na tela

import pytest


@pytest.fixture(scope="session", autouse=True)
def fechar_qt_antes_de_sair():
    # janelas presas em QTimer.singleShot sobreviviam até o fim do Python e eram destruídas depois do
    # QApplication: o processo caía (0xC0000005) depois de todos os testes passarem
    yield
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for janela in app.topLevelWidgets():
        janela.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


@pytest.fixture(autouse=True)
def sem_janelas_de_verdade(monkeypatch):
    # o pet explorando não pode pular pras janelas reais de quem roda os testes
    from mascote import explorar

    monkeypatch.setattr(explorar, "lugares", lambda *a, **kw: [])
    monkeypatch.setattr(explorar, "janela_embaixo", lambda *a, **kw: None)


@pytest.fixture(autouse=True)
def dados_temporarios(tmp_path, monkeypatch):
    monkeypatch.setenv("MASCOTE_DADOS", str(tmp_path / "dados"))


@pytest.fixture(autouse=True)
def registro_temporario(monkeypatch):
    import winreg

    chave = rf"Software\MascoteTeste{os.getpid()}"
    monkeypatch.setenv("MASCOTE_REGISTRO", chave)
    yield
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, chave)
    except OSError:
        pass
