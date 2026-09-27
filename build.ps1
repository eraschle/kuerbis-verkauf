# Baut dist\Kuerbisverkauf.exe (eine einzelne Datei, ohne Konsolenfenster)
# (kein ErrorActionPreference=Stop: PyInstaller schreibt Infos auf stderr; geprüft wird der Exit-Code)
Set-Location $PSScriptRoot

uv run pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests fehlgeschlagen - kein Build." }

uv run pyinstaller --noconfirm --clean --onefile --windowed `
    --name Kuerbisverkauf `
    --icon src/kuerbis/web/kuerbis.ico `
    --paths src `
    --add-data "src/kuerbis/web;kuerbis/web" `
    src/kuerbis/app.py
if ($LASTEXITCODE -ne 0) { throw "Build fehlgeschlagen." }

Write-Host "Fertig: $PSScriptRoot\dist\Kuerbisverkauf.exe"
