# Baixa o llama-server (Vulkan) para recursos\llama. O modelo é baixado pelo instalador (mascote/baixar.py).
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$llama = Join-Path $raiz "recursos\llama"
New-Item -ItemType Directory -Force $llama | Out-Null

# Versão fixa e conferida. Para atualizar: troque a tag e o SHA-256 (campo "digest" do asset na API do GitHub).
$tag = "b11941"
$sha256 = "3383EFCA87453D1D1E564B91D95DB16D5B511EC72FAD4983FD99EA8774649FD6"

if (-not (Test-Path (Join-Path $llama "llama-server.exe"))) {
    $zip = Join-Path $env:TEMP "mascote-llama.zip"
    Write-Host "Baixando llama.cpp $tag (Vulkan)..."
    Invoke-WebRequest "https://github.com/ggml-org/llama.cpp/releases/download/$tag/llama-$tag-bin-win-vulkan-x64.zip" -OutFile $zip
    if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne $sha256) { Remove-Item $zip; throw "SHA-256 do llama.cpp não confere; abortando." }
    Expand-Archive $zip -DestinationPath $llama -Force
    Remove-Item $zip
    # alguns zips trazem uma subpasta; achata
    $exe = Get-ChildItem $llama -Recurse -Filter "llama-server.exe" | Select-Object -First 1
    if ($exe.DirectoryName -ne $llama) { Get-ChildItem $exe.DirectoryName | Move-Item -Destination $llama -Force }
    Set-Content (Join-Path $llama "VERSAO.txt") $tag -Encoding utf8
}

Write-Host "Pronto: llama.cpp $(Get-Content (Join-Path $llama 'VERSAO.txt'))"
