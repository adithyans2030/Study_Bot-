# Backs up the database every night at 3 AM while you are logged in (same no-admin, no-stored-
# password login type as install_autostart.ps1 — Windows' "run whether logged on or not" option
# needs admin rights to register). If the PC is off, asleep, or you are logged out at 3 AM, it runs
# as soon as you are next logged in.
#
#   powershell -ExecutionPolicy Bypass -File scripts\install_backup_task.ps1              # install
#   powershell -ExecutionPolicy Bypass -File scripts\install_backup_task.ps1 -Uninstall   # remove
param([switch]$Uninstall)
$ErrorActionPreference = "Stop"
$TaskName = "StudyBot Backup"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed the '$TaskName' scheduled task."
    exit 0
}

$repo = Split-Path -Parent $PSScriptRoot
$backupScript = Join-Path $repo "scripts\backup.ps1"
if (-not (Test-Path $backupScript)) { throw "Not found: $backupScript" }

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$backupScript`""
$trigger = New-ScheduledTaskTrigger -Daily -At "3:00AM"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Description "Nightly StudyBot database backup." -Force | Out-Null

Write-Host "Installed. First backup runs tonight at 3 AM (or as soon as the PC is on after that)."
Write-Host "Run one right now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Remove it later:    powershell -ExecutionPolicy Bypass -File scripts\install_backup_task.ps1 -Uninstall"
