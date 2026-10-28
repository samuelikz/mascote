# Baixa o llama-server (Vulkan) e copia a Gemma 2 9B do Ollama para recursos\. Pode rodar de novo sem problema.
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$llama = Join-Path $raiz "recursos\llama"
$modelo = Join-Path $raiz "recursos\modelo"
New-Item -ItemType Directory -Force $llama, $modelo | Out-Null

if (-not (Test-Path (Join-Path $llama "llama-server.exe"))) {
    # "latest" às vezes aponta para uma release sem binários; pega a mais nova que tenha o zip Vulkan x64.
    $releases = Invoke-RestMethod "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=20"
    $asset = $null
    foreach ($r in $releases) {
        $asset = $r.assets | Where-Object { $_.name -like "llama-*-bin-win-vulkan-x64.zip" } | Select-Object -First 1
        if ($asset) { $tag = $r.tag_name; break }
    }
    if (-not $asset) { throw "Nenhuma release do llama.cpp com win-vulkan-x64 encontrada." }
    $zip = Join-Path $env:TEMP $asset.name
    Write-Host "Baixando $($asset.name)..."
    Invoke-WebRequest $asset.browser_download_url -OutFile $zip
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
