param(
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$LogDir = Join-Path $Root "tmp\local-dev"
$ApiBaseUrl = "http://127.0.0.1:$BackendPort"
$FrontendUrl = "http://127.0.0.1:$FrontendPort"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 300
    } catch {
        return $false
    }
}

function Test-BackendReady {
    if (-not (Test-HttpOk "$ApiBaseUrl/health")) {
        return $false
    }
    return Test-HttpOk "$ApiBaseUrl/api/products/unbound-ad-sources"
}

function Get-ListeningProcessIds {
    param([int]$Port)
    $lines = netstat -ano | Select-String ":$Port\s+.*LISTENING"
    $ids = @()
    foreach ($line in $lines) {
        $parts = ($line.ToString() -split "\s+") | Where-Object { $_ }
        if ($parts.Length -ge 5) {
            $ids += [int]$parts[-1]
        }
    }
    return $ids | Sort-Object -Unique
}

function Stop-PortListeners {
    param([int]$Port)
    foreach ($processId in Get-ListeningProcessIds -Port $Port) {
        Stop-Process -Id $processId -Force
    }
}

function Test-FrontendApiBase {
    param(
        [string]$ExpectedApiBaseUrl,
        [string]$FrontendUrl
    )
    try {
        $module = Invoke-WebRequest -Uri "$FrontendUrl/src/api.ts" -UseBasicParsing -TimeoutSec 5
        return $module.Content.Contains("`"VITE_API_BASE_URL`": `"$ExpectedApiBaseUrl`"")
    } catch {
        return $false
    }
}

function Start-Backend {
    if (Test-BackendReady) {
        Write-Host "Backend ready: $ApiBaseUrl"
        return
    }
    if (Test-HttpOk "$ApiBaseUrl/health") {
        Write-Host "Backend port is running an old API. Restarting port $BackendPort."
        Stop-PortListeners -Port $BackendPort
        Start-Sleep -Seconds 1
    }

    $outLog = Join-Path $LogDir "backend.out.log"
    $errLog = Join-Path $LogDir "backend.err.log"
    $command = "Set-Location '$BackendDir'; python -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort 1> '$outLog' 2> '$errLog'"
    Start-Process -FilePath powershell.exe -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $command -WindowStyle Hidden | Out-Null

    for ($i = 0; $i -lt 30; $i++) {
        if (Test-BackendReady) {
            Write-Host "Backend started: $ApiBaseUrl"
            return
        }
        Start-Sleep -Milliseconds 500
    }

    throw "Backend did not start. Check $errLog"
}

function Start-Frontend {
    if (Test-HttpOk $FrontendUrl) {
        if (Test-FrontendApiBase -ExpectedApiBaseUrl $ApiBaseUrl -FrontendUrl $FrontendUrl) {
            Write-Host "Frontend ready: $FrontendUrl -> $ApiBaseUrl"
            return
        }
        Write-Host "Frontend port is using a different API base. Restarting port $FrontendPort."
        Stop-PortListeners -Port $FrontendPort
        Start-Sleep -Seconds 1
    }

    $outLog = Join-Path $LogDir "frontend.out.log"
    $errLog = Join-Path $LogDir "frontend.err.log"
    $command = "`$env:VITE_API_BASE_URL='$ApiBaseUrl'; Set-Location '$FrontendDir'; npm run dev 1> '$outLog' 2> '$errLog'"
    Start-Process -FilePath powershell.exe -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $command -WindowStyle Hidden | Out-Null

    for ($i = 0; $i -lt 40; $i++) {
        if ((Test-HttpOk $FrontendUrl) -and (Test-FrontendApiBase -ExpectedApiBaseUrl $ApiBaseUrl -FrontendUrl $FrontendUrl)) {
            Write-Host "Frontend started: $FrontendUrl -> $ApiBaseUrl"
            return
        }
        Start-Sleep -Milliseconds 500
    }

    throw "Frontend did not start with $ApiBaseUrl. Check $errLog"
}

Start-Backend
Start-Frontend

Write-Host "Local dev is ready."
Write-Host "Backend:  $ApiBaseUrl"
Write-Host "Frontend: $FrontendUrl"
