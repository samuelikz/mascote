# Gera dist\Mascote.msi (só o app; a IA é baixada durante a instalação).
# Pré-requisito: WiX 5
#   dotnet tool install --global wix --version 5.0.2
#   wix extension add -g WixToolset.UI.wixext/5.0.2 WixToolset.Util.wixext/5.0.2
# sem "Stop": no PowerShell 5.1 o stderr de exe nativo vira erro; conferimos $LASTEXITCODE em cada passo
param([string]$Versao = "1.2.0")
Set-Location $PSScriptRoot
$py = ".venv\Scripts\python.exe"

& $py -m pytest tests -q
if ($LASTEXITCODE) { throw "testes falharam" }

$env:PYTHONPATH = $PSScriptRoot
& $py ferramentas\imagens.py instalador
if ($LASTEXITCODE) { throw "imagens falharam" }

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

wix build instalador\Mascote.wxs -d Versao=$Versao -culture pt-BR -arch x64 `
    -ext WixToolset.UI.wixext -ext WixToolset.Util.wixext -b instalador -o dist\Mascote.msi
if ($LASTEXITCODE) { throw "WiX falhou" }
wix build instalador\Mascote.wxs -d Versao=$Versao -d Teste=1 -culture pt-BR -arch x64 `
    -ext WixToolset.UI.wixext -ext WixToolset.Util.wixext -b instalador -o dist\Mascote-teste.msi
if ($LASTEXITCODE) { throw "WiX (teste) falhou" }
Write-Host "Pronto: dist\Mascote.msi e dist\Mascote-teste.msi"
