# Windows Task Scheduler: Set up 48-hour GitHub refresh task
# Run this in admin PowerShell

$taskName = "linkedn-48h-github-refresh"
$taskPath = "\"
$scriptPath = "G:\Claude Projects\Asistanlar\linkedn\git-refresh.ps1"

# Delete task if exists
Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false

# Create new task
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00"
$settings = New-ScheduledTaskSettingsSet -RunOnlyIfNetworkAvailable -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -Action $action -Trigger $trigger -TaskName $taskName -TaskPath $taskPath -Description "LinkedIn Assistant GitHub refresh every 48 hours" -Principal $principal -Settings $settings -Force

Write-Host "Task created: $taskName"
Write-Host "Schedule: Daily at 02:00"
Write-Host "Action: Auto push if 48 hours have passed"
