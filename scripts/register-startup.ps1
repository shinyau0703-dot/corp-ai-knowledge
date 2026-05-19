# 需要以系統管理員身分執行
# 執行方式：右鍵 PowerShell -> 以系統管理員身分執行，然後輸入：
# powershell -ExecutionPolicy Bypass -File "D:\Sandy\KMsystem\corp-ai-knowledge\scripts\register-startup.ps1"

$root = "D:\Sandy\KMsystem\corp-ai-knowledge\scripts"

# 後端服務
$actionB = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$root\start-backend.bat`""
$triggerB = New-ScheduledTaskTrigger -AtStartup
$settingsB = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask `
    -TaskName "KM-Backend" `
    -Action $actionB `
    -Trigger $triggerB `
    -Settings $settingsB `
    -RunLevel Highest `
    -Force
Write-Host "[OK] KM-Backend 工作已註冊"

# 前端服務（延遲 20 秒，等後端先起來）
$actionF = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$root\start-frontend.bat`""
$triggerF = New-ScheduledTaskTrigger -AtStartup
$triggerF.Delay = "PT20S"
$settingsF = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask `
    -TaskName "KM-Frontend" `
    -Action $actionF `
    -Trigger $triggerF `
    -Settings $settingsF `
    -RunLevel Highest `
    -Force
Write-Host "[OK] KM-Frontend 工作已註冊"

Write-Host ""
Write-Host "完成！重開機後服務會自動啟動。"
Write-Host "可在「工作排程器」中查看 KM-Backend / KM-Frontend 工作。"
