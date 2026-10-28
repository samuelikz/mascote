# Gera dist\MascoteSetup.exe (só o app; a IA é baixada durante a instalação).
# Pré-requisito: Inno Setup 6 (winget install JRSoftware.InnoSetup)
# sem "Stop": no PowerShell 5.1 o stderr de exe nativo vira erro; conferimos $LASTEXITCODE em cada passo
# -Publicar: cria a release v$Versao no GitHub com os dois instaladores (o pet acha em "Verificar atualizações")
param([string]$Versao = "1.2.0", [switch]$Publicar)
Set-Location $PSScriptRoot
$py = ".venv\Scripts\python.exe"
"# gerado pelo build.ps1 (-Versao); não edite à mão`nVERSAO = `"$Versao`"" | Set-Content -Encoding utf8 mascote\versao.py

# o pet aberto prende a GPU com a Gemma e os testes da IA de verdade não conseguem subir outro llama-server
Get-Process Mascote, llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
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

if ($Publicar) {
    $gh = if (Get-Command gh -ErrorAction SilentlyContinue) { "gh" } else { ".ferramentas\gh\bin\gh.exe" }
    & $gh release create "v$Versao" dist\MascoteSetup.exe dist\Mascote-teste-setup.exe -R samuelikz/mascote --title "Mascote $Versao" --generate-notes
    if ($LASTEXITCODE) { throw "gh release falhou" }
    Write-Host "Publicado: v$Versao"
}
