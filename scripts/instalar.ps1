param([string]$Python = '')
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location $projectRoot
try {
    if (!(Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        $runtimePython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
        if ($Python) { $pythonExe = $Python }
        elseif (Test-Path -LiteralPath $runtimePython) { $pythonExe = $runtimePython }
        else {
            $pythonExe = (& py -3 -c 'import sys; print(sys.executable)')
            if ($LASTEXITCODE -ne 0) { throw 'Instala Python 3.11 o posterior, o indica -Python con su ruta.' }
        }
        & $pythonExe -c 'import sys; assert sys.version_info >= (3, 11), "Se requiere Python 3.11 o posterior"'
        if ($LASTEXITCODE -ne 0) { throw 'Version de Python no compatible.' }
        & $pythonExe -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno virtual.' }
    }
    $pythonMinor = [int](& '.\.venv\Scripts\python.exe' -c 'import sys; print(sys.version_info.minor)')
    # The verified lock uses NumPy 2.5 (Python >= 3.12); Python 3.11 resolves compatible versions.
    $requirements = if ($pythonMinor -ge 12 -and (Test-Path -LiteralPath 'requirements.lock.txt')) { 'requirements.lock.txt' } else { 'requirements.txt' }
    & '.\.venv\Scripts\python.exe' -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias de Python.' }
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        & npm.cmd ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias del frontend. Verifica Node.js 22 o posterior.' }
    } finally { Pop-Location }
    Write-Host 'Instalacion completa. Ejecuta iniciar.cmd.' -ForegroundColor Cyan
} finally { Pop-Location }
