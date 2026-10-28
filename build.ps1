# Gera dist\instalador\MascoteSetup.exe (+ .bin). Pré-requisito: ferramentas\preparar_recursos.ps1 já rodado.
# sem "Stop": no PowerShell 5.1 o stderr de exe nativo vira erro; conferimos $LASTEXITCODE em cada passo
Set-Location $PSScriptRoot
$py = ".venv\Scripts\python.exe"

& $py -m pytest tests -q
if ($LASTEXITCODE) { throw "testes falharam" }
if (-not (Test-Path "recursos\modelo\gemma2-9b.gguf")) { throw "rode ferramentas\preparar_recursos.ps1 antes" }

$env:PYTHONPATH = $PSScriptRoot
& $py ferramentas\icone.py instalador\icone.ico
if ($LASTEXITCODE) { throw "ícone falhou" }

& $py -m PyInstaller --noconfirm --onedir --windowed --name Mascote --icon instalador\icone.ico `
    --distpath dist --workpath build run_mascote.py
if ($LASTEXITCODE) { throw "PyInstaller falhou" }

$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1 }
if (-not $iscc) { throw "Inno Setup não encontrado: winget install JRSoftware.InnoSetup" }
& $iscc instalador\mascote.iss
if ($LASTEXITCODE) { throw "Inno Setup falhou" }
Write-Host "Pronto: dist\instalador\"
