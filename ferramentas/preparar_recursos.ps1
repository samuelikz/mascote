# Baixa o llama-server (Vulkan) e copia a Gemma 2 9B do Ollama para recursos\. Pode rodar de novo sem problema.
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$llama = Join-Path $raiz "recursos\llama"
$modelo = Join-Path $raiz "recursos\modelo"
New-Item -ItemType Directory -Force $llama, $modelo | Out-Null

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

$destino = Join-Path $modelo "gemma2-9b.gguf"
if (-not (Test-Path $destino)) {
    $ollama = Join-Path $env:USERPROFILE ".ollama\models"
    $manifesto = Get-Content (Join-Path $ollama "manifests\registry.ollama.ai\library\gemma2\9b") -Raw | ConvertFrom-Json
    $digest = ($manifesto.layers | Where-Object { $_.mediaType -eq "application/vnd.ollama.image.model" }).digest
    $blob = Join-Path $ollama ("blobs\" + $digest.Replace(":", "-"))
    Write-Host "Copiando modelo de $blob..."
    Copy-Item $blob $destino
}

Write-Host "Pronto: $(Get-Content (Join-Path $llama 'VERSAO.txt')) + $([math]::Round((Get-Item $destino).Length/1GB,1)) GB"
