@echo off
cd /d "%~dp0"
set /p V="Versao (ex.: 1.2.1): "
set /p P="Publicar no GitHub? (s/n): "
set EXTRA=
if /i "%P"=="s" set EXTRA=-Publicar
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1 -Versao %V% %EXTRA% > build.log 2>&1
echo FIM %ERRORLEVEL% >> build.log
type build.log | findstr /i "Pronto Publicado falhou FIM"
pause
