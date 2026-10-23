param(
    [Parameter(Mandatory)][string]$Python,
    [Parameter(Mandatory)][string]$Origin,
    [Parameter(Mandatory)][string]$OffsiteDirectory,
    [Parameter(Mandatory)][string]$DeletionStateDirectory,
    [Parameter(Mandatory)][string]$CheckpointDirectory,
    [Parameter(Mandatory)][string]$ReportDirectory,
    [Parameter(Mandatory)][string]$DiskPath,
    [string]$TelegramConfig
)
$ErrorActionPreference = 'Stop'
$watchdogScript = Join-Path $PSScriptRoot 'watchdog.py'
$Python = (Resolve-Path -LiteralPath $Python).Path
$taskPython = Join-Path (Split-Path -Parent $Python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $taskPython -PathType Leaf)) { throw 'Matching pythonw.exe is required.' }
foreach ($directory in @($OffsiteDirectory, $DeletionStateDirectory, $CheckpointDirectory, $ReportDirectory, $DiskPath)) {
    if (-not [IO.Path]::IsPathRooted($directory) -or -not (Test-Path -LiteralPath $directory -PathType Container)) { throw 'Use existing absolute directories.' }
}
$watchdogValues = @($watchdogScript, '--origin', $Origin, '--offsite-directory', $OffsiteDirectory, '--deletion-state-directory', $DeletionStateDirectory, '--checkpoint-directory', $CheckpointDirectory, '--disk-path', $DiskPath, '--report-directory', $ReportDirectory)
if ($TelegramConfig) {
    $TelegramConfig = (Resolve-Path -LiteralPath $TelegramConfig).Path
    $watchdogValues += @('--telegram-config', $TelegramConfig)
}
foreach ($argument in $watchdogValues) {
    if ($argument.Contains('"') -or $argument.Contains("`n") -or $argument.Contains("`r")) { throw 'Invalid task argument.' }
}
$taskArguments = ($watchdogValues | ForEach-Object { '"' + [regex]::Replace($_, '(\\+)$', '$1$1') + '"' }) -join ' '
# Require a real healthy baseline before installing the repeating check.
& $Python @watchdogValues
if ($LASTEXITCODE -ne 0) { throw 'Initial watchdog check failed; task was not registered.' }
$action = New-ScheduledTaskAction -Execute $taskPython -Argument $taskArguments -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'PolicyLens-Operational-Watchdog' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Read-only health checks every five minutes while signed in; local reports and optional configured Telegram alerts.' -Force | Select-Object TaskName, State
