# Runs the StudyBot API for real use: no auto-reload, restarts itself if it crashes, and sends
# all output to log files instead of a console window (this is what Task Scheduler launches).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\run.ps1
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$sbHome = if ($env:STUDYBOT_HOME) { $env:STUDYBOT_HOME } else { Join-Path $env:LOCALAPPDATA "StudyBot" }
$python = Join-Path $sbHome "venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Virtualenv missing. Run scripts\setup.ps1 first." }

$port = if ($env:STUDYBOT_PORT) { $env:STUDYBOT_PORT } else { "8000" }
$logDir = Join-Path $sbHome "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$eventsLog = Join-Path $logDir "console.log"        # one short line per start/stop; kept forever
$outLog = Join-Path $logDir "server-out.log"        # uvicorn's own output; overwritten each (re)start
$errLog = Join-Path $logDir "server-err.log"

if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
    "$(Get-Date -Format o) already running on port $port; not starting a second copy." | Add-Content $eventsLog
    exit 0
}

# uvicorn writes its own log to stderr; that is normal, not a failure, so it must NOT be routed
# through PowerShell's success/error streams (which would turn a startup banner into a terminating
# error under $ErrorActionPreference = "Stop"). Start-Process redirects at the OS level instead.
Set-Location (Join-Path $repo "backend")
while ($true) {
    "$(Get-Date -Format o) starting StudyBot on port $port" | Add-Content $eventsLog
    $proc = Start-Process -FilePath $python -NoNewWindow -PassThru -Wait `
        -ArgumentList @("-m", "uvicorn", "app.main:create_app", "--factory", "--host", "127.0.0.1", "--port", $port) `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    "$(Get-Date -Format o) server exited (code $($proc.ExitCode)); see server-out.log / server-err.log; restarting in 5s" `
        | Add-Content $eventsLog
    Start-Sleep -Seconds 5
}
