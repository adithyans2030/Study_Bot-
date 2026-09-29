# Makes StudyBot start automatically when you log into Windows, and restart itself if it crashes.
# No admin rights needed: it only runs while you are logged in (a "run whether logged on or not"
# service needs an admin-stored password; this project stays a personal, at-login tool instead).
#
#   powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1              # install
#   powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1 -Uninstall   # remove
#
# After installing: log off and back on (or reboot) and check http://127.0.0.1:8000, or start it
# immediately with: Start-ScheduledTask -TaskName StudyBot
param([switch]$Uninstall)
$ErrorActionPreference = "Stop"
$TaskName = "StudyBot"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed the '$TaskName' scheduled task. It will not start at your next login."
    exit 0
}

$repo = Split-Path -Parent $PSScriptRoot
$runScript = Join-Path $repo "scripts\run.ps1"
if (-not (Test-Path $runScript)) { throw "Not found: $runScript" }

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runScript`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Description "Starts the StudyBot web app when $env:USERNAME logs in." -Force | Out-Null

Write-Host "Installed. StudyBot will start next time you log in."
Write-Host "Start it right now:   Start-ScheduledTask -TaskName $TaskName"
Write-Host "Remove it later:      powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1 -Uninstall"
