# ECOTIME bot — uzilganda qayta tiklash. Token: telegram_token.txt yoki bot.env
# Jurnal: bot_24x7.log (shu papkada)

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

function Write-BotLog([string]$Message) {
    try {
        $logPath = Join-Path $PSScriptRoot "bot_24x7.log"
        Add-Content -Path $logPath -Encoding UTF8 -Value ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message)
    } catch { }
}

function Get-PythonLaunch {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return @{ Exe = $python.Source; Args = @() } }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return @{ Exe = $py.Source; Args = @("-3") } }
    $roots = @(
        "$env:LOCALAPPDATA\Programs\Python",
        "$env:ProgramFiles\Python311",
        "${env:ProgramFiles(x86)}\Python311",
        "$env:ProgramFiles\Python312",
        "$env:ProgramFiles\Python313"
    )
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        $exe = Join-Path $root "python.exe"
        if (Test-Path $exe) { return @{ Exe = $exe; Args = @() } }
        $found = Get-ChildItem -Path $root -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { return @{ Exe = $found.FullName; Args = @() } }
    }
    return $null
}

function Import-BotEnv {
    $envPath = Join-Path $PSScriptRoot "bot.env"
    if (-not (Test-Path $envPath)) { return }
    Get-Content $envPath -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { return }
        $name = $line.Substring(0, $eq).Trim()
        $val = $line.Substring($eq + 1).Trim()
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith([char]39) -and $val.EndsWith([char]39))) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        Set-Item -Path "env:$name" -Value $val
    }
}

function Test-HasBotToken {
    Import-BotEnv
    if ($env:TELEGRAM_BOT_TOKEN -and $env:TELEGRAM_BOT_TOKEN.Trim()) { return $true }
    $p = Join-Path $PSScriptRoot "telegram_token.txt"
    if (-not (Test-Path $p)) { return $false }
    foreach ($line in Get-Content $p -Encoding UTF8) {
        $l = $line.Trim()
        if ($l -and -not $l.StartsWith("#") -and $l.Contains(":")) { return $true }
    }
    return $false
}

$launch = Get-PythonLaunch
if (-not $launch) {
    Write-BotLog "XATO: Python topilmadi. python.org dan o'rnating yoki PATH ga qo'shing."
    Write-Host "Python topilmadi. bot_24x7.log ga yozildi." -ForegroundColor Red
}

if (-not (Test-HasBotToken)) {
    Write-BotLog "XATO: Token topilmadi (telegram_token.txt yoki bot.env)."
    Write-Host "TOKEN topilmadi. telegram_token.txt yoki bot.env qo'shing." -ForegroundColor Red
}

Write-BotLog "run_24x7 ishga tushdi. Papka: $PSScriptRoot"

while ($true) {
    Import-BotEnv
    $launch = Get-PythonLaunch
    if (-not $launch) {
        Write-BotLog "Kutilmoqda: Python yo'q. 60 s keyin qayta."
        Start-Sleep -Seconds 60
        continue
    }
    if (-not (Test-HasBotToken)) {
        Write-BotLog "Kutilmoqda: token yo'q. 60 s keyin qayta."
        Start-Sleep -Seconds 60
        continue
    }

    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$ts] Bot ishga tushmoqda..."
    Write-BotLog "python ishga tushmoqda: $($launch.Exe) $($launch.Args -join ' ') bot.py"

    $argList = @($launch.Args + @((Join-Path $PSScriptRoot "bot.py")))
    $code = -1
    try {
        $p = Start-Process -FilePath $launch.Exe -ArgumentList $argList -WorkingDirectory $PSScriptRoot -Wait -PassThru -NoNewWindow
        if ($null -ne $p.ExitCode) { $code = $p.ExitCode }
    } catch {
        Write-BotLog ("Start-Process xato: {0}" -f $_)
    }

    $ts2 = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-BotLog "python tugadi. chiqish kodi: $code"
    Write-Host "[$ts2] Chiqish: $code. 10 s keyin qayta..."
    Start-Sleep -Seconds 10
}
