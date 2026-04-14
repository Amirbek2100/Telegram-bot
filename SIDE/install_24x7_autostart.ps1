# Windows: kirishda botni yashirin oynada ishga tushirish (WorkingDirectory bilan).
# O'ng tugma - Run with PowerShell, yoki Administrator (agar xato bersa).

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runPs1 = Join-Path $dir "run_24x7.ps1"

if (-not (Test-Path $runPs1)) {
    Write-Host "run_24x7.ps1 topilmadi: $runPs1"
    exit 1
}

$taskName = "ECOTIME-Telegram-Bot"
$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runPs1`""
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

try {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg -WorkingDirectory $dir
} catch {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg
}

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$principalHi = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principalHi -Settings $settings -Force | Out-Null
} catch {
    $principalLo = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principalLo -Settings $settings -Force | Out-Null
}

Write-Host ""
Write-Host "TAYYOR: vazifa '$taskName'"
Write-Host "Windows ga kirganingizda bot yashirin ishlaydi."
Write-Host "Jurnal: $(Join-Path $dir 'bot_24x7.log')"
Write-Host "O'chirish: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
Write-Host ""
