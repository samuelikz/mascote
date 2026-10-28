# Remove todas as instalações do Mascote (MSI antigo ou Inno Setup). Memórias e lembretes ficam em %LOCALAPPDATA%.
# Os erros 2503/2504 do MSI acontecem quando o msiexec roda sem administrador: este script se eleva antes.
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole("Administrators")) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}
Get-Process Mascote, llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
$chaves = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
          "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
          "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*"
$achados = Get-ItemProperty $chaves -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like "Mascote*" }
if (-not $achados) { Write-Host "Nenhum Mascote instalado." }
foreach ($a in $achados) {
    Write-Host "Removendo $($a.DisplayName) $($a.DisplayVersion)..."
    $codigo = Split-Path $a.PSPath -Leaf
    if ($codigo -match '^\{[0-9A-F-]+\}$' -and $a.WindowsInstaller -eq 1) {
        $p = Start-Process msiexec.exe -ArgumentList "/x $codigo /qb /norestart" -Wait -PassThru
        Write-Host "  msiexec terminou com código $($p.ExitCode)"
    } elseif ($a.UninstallString) {
        $exe = ($a.UninstallString -replace '"', '')
        $p = Start-Process $exe -ArgumentList "/SILENT /SUPPRESSMSGBOXES /NORESTART" -Wait -PassThru
        Write-Host "  desinstalador terminou com código $($p.ExitCode)"
    }
}
Get-ItemProperty $chaves -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like "Mascote*" } |
    ForEach-Object { Write-Host "AINDA INSTALADO: $($_.DisplayName) -> $($_.PSPath)" }
Read-Host "Pronto. Enter para fechar"
