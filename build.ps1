# Gera dist\Mascote.msi. Pré-requisitos: ferramentas\preparar_recursos.ps1 já rodado (llama.cpp) e
# WiX 5: dotnet tool install --global wix --version 5.0.2
#        wix extension add -g WixToolset.UI.wixext/5.0.2 WixToolset.Util.wixext/5.0.2
# sem "Stop": no PowerShell 5.1 o stderr de exe nativo vira erro; conferimos $LASTEXITCODE em cada passo
param([string]$Versao = "1.1.0")
Set-Location $PSScriptRoot
$py = ".venv\Scripts\python.exe"

& $py -m pytest tests -q
if ($LASTEXITCODE) { throw "testes falharam" }
if (-not (Test-Path "recursos\llama\llama-server.exe")) { throw "rode ferramentas\preparar_recursos.ps1 antes" }

$env:PYTHONPATH = $PSScriptRoot
& $py ferramentas\imagens.py instalador
if ($LASTEXITCODE) { throw "imagens falharam" }

& $py -m PyInstaller --noconfirm --onedir --windowed --name Mascote --icon instalador\icone.ico `
    --distpath dist --workpath build run_mascote.py
if ($LASTEXITCODE) { throw "PyInstaller falhou" }

wix build instalador\Mascote.wxs -d Versao=$Versao -culture pt-BR -arch x64 `
    -ext WixToolset.UI.wixext -ext WixToolset.Util.wixext `
    -b instalador -o dist\Mascote.msi
if ($LASTEXITCODE) { throw "WiX falhou" }
Write-Host "Pronto: dist\Mascote.msi"
