# Gera dist\MascoteSetup.exe (só o app; a IA é baixada durante a instalação).
# Pré-requisito: Inno Setup 6 (winget install JRSoftware.InnoSetup)
# sem "Stop": no PowerShell 5.1 o stderr de exe nativo vira erro; conferimos $LASTEXITCODE em cada passo
param([string]$Versao = "1.2.0")
Set-Location $PSScriptRoot
$py = ".venv\Scripts\python.exe"

& $py -m pytest tests -q
if ($LASTEXITCODE) { throw "testes falharam" }

& $py -m PyInstaller --noconfirm --onedir --windowed --name Mascote --icon instalador\icone.ico `
    --distpath dist --workpath build run_mascote.py
if ($LASTEXITCODE) { throw "PyInstaller falhou" }

# partes do Qt que o pet não usa (OpenGL por software, QML/Quick, PDF, rede, teclado virtual, traduções)
$qt = "dist\Mascote\_internal\PySide6"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue @(
    "$qt\opengl32sw.dll", "$qt\Qt6Pdf.dll", "$qt\Qt6Qml*.dll", "$qt\Qt6Quick.dll", "$qt\Qt6VirtualKeyboard.dll",
    "$qt\Qt6Network.dll", "$qt\QtNetwork.pyd", "$qt\translations", "$qt\plugins\tls", "$qt\plugins\networkinformation",
    "$qt\plugins\imageformats\qpdf.dll"
)

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
& $iscc /Q /DVersao=$Versao instalador\mascote.iss
if ($LASTEXITCODE) { throw "Inno Setup falhou" }
& $iscc /Q /DVersao=$Versao /DTeste=1 instalador\mascote.iss
if ($LASTEXITCODE) { throw "Inno Setup (teste) falhou" }
Write-Host "Pronto: dist\MascoteSetup.exe e dist\Mascote-teste-setup.exe"
