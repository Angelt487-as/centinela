param([switch]$SoloVerificar)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$vitePath = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
if (!(Test-Path -LiteralPath $pythonPath) -or !(Test-Path -LiteralPath $vitePath)) { throw 'Ejecuta instalar.cmd antes de iniciar.' }
$occupied = Get-NetTCPConnection -LocalPort 8000,5173 -State Listen -ErrorAction SilentlyContinue
if ($occupied) { throw 'El puerto 8000 o 5173 ya esta ocupado. Cierra la instancia anterior antes de iniciar.' }
$logDir = Join-Path $projectRoot 'data\logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$backendProcess = $null
$frontendProcess = $null
try {
    $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000','--no-access-log','--no-proxy-headers') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'backend-out.log') -RedirectStandardError (Join-Path $logDir 'backend-error.log')
    $nodePath = (Get-Command node.exe -ErrorAction Stop).Source
    $frontendProcess = Start-Process -FilePath $nodePath -ArgumentList @(('"' + $vitePath + '"'),'--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'frontend-out.log') -RedirectStandardError (Join-Path $logDir 'frontend-error.log')
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
            $page = Invoke-WebRequest 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2
            if ($health.status -eq 'ok' -and $page.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 500 }
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) { break }
    }
    if (!$ready) { throw 'No se pudo iniciar. Consulta data\logs para obtener el diagnostico.' }
    Write-Host 'Centinela 360 esta listo en http://127.0.0.1:5173/' -ForegroundColor Cyan
    Write-Host 'API y documentacion: http://127.0.0.1:8000/docs'
    $authStatus = Invoke-RestMethod 'http://127.0.0.1:8000/api/auth/csrf' -TimeoutSec 2
    if ($authStatus.setup_required) { Write-Host 'Primer acceso: ejecuta crear-administrador.cmd para elegir tu usuario y contrasena.' -ForegroundColor Yellow }
    if (!$SoloVerificar) { Read-Host 'Abre la URL en tu navegador. Pulsa Enter aqui para detener ambos servidores' | Out-Null }
} finally {
    foreach ($ownedProcess in @($backendProcess, $frontendProcess)) {
        if ($ownedProcess -and !$ownedProcess.HasExited) { Stop-Process -Id $ownedProcess.Id -ErrorAction SilentlyContinue }
    }
}
