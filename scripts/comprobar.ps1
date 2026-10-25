param([switch]$UI)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location $projectRoot
try {
    New-Item -ItemType Directory -Path 'data' -Force | Out-Null
    & '.\.venv\Scripts\python.exe' -m pytest backend/tests --basetemp data/test-current -q
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas de backend.' }
    if ($UI) {
        Write-Host 'Se crearan cuentas aleatorias y servidores de QA aislados. Requiere Edge y puertos 8000/5173 libres.'
        & '.\.venv\Scripts\python.exe' scripts\probar_interfaz.py
        if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas de interfaz.' }
        return
    }
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Fallo la compilacion del frontend.' }
    } finally { Pop-Location }
} finally { Pop-Location }
