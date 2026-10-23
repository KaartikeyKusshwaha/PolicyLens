param(
    [Parameter(Mandatory)][string]$Python,
    [Parameter(Mandatory)][string]$SshTarget,
    [Parameter(Mandatory)][string]$Identity,
    [Parameter(Mandatory)][string]$KnownHosts,
    [Parameter(Mandatory)][string]$EncryptionKey,
    [Parameter(Mandatory)][string]$Destination,
    [string]$DatabaseKey,
    [string]$DeletionStateDestination,
    [string]$CheckpointDestination,
    [string]$CheckpointFingerprint
)
$ErrorActionPreference = 'Stop'
$backupScript = Join-Path $PSScriptRoot 'pull_backup.py'
$backupPaths = @($Python, $backupScript, $Identity, $KnownHosts, $EncryptionKey)
if ($DatabaseKey) { $backupPaths += $DatabaseKey }
foreach ($backupPath in $backupPaths) {
    if (-not (Test-Path -LiteralPath $backupPath -PathType Leaf)) { throw "Required backup file is unavailable: $backupPath" }
}
$Python = (Resolve-Path -LiteralPath $Python).Path
$Identity = (Resolve-Path -LiteralPath $Identity).Path
$KnownHosts = (Resolve-Path -LiteralPath $KnownHosts).Path
$EncryptionKey = (Resolve-Path -LiteralPath $EncryptionKey).Path
if ($DatabaseKey) { $DatabaseKey = (Resolve-Path -LiteralPath $DatabaseKey).Path }
if ($DeletionStateDestination -and -not $DatabaseKey) { throw 'Deletion history requires DatabaseKey.' }
if ($DeletionStateDestination) { $DeletionStateDestination = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DeletionStateDestination) }
if ([bool]$CheckpointDestination -ne [bool]$CheckpointFingerprint) { throw 'Checkpoint copies require destination and trusted fingerprint.' }
if ($CheckpointFingerprint -and $CheckpointFingerprint -notmatch '^[a-f0-9]{64}$') { throw 'Invalid trusted checkpoint fingerprint.' }
if ($CheckpointDestination) { $CheckpointDestination = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($CheckpointDestination) }
$Destination = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Destination)
if ($SshTarget -notmatch '^[A-Za-z_][A-Za-z0-9_-]*@[A-Za-z0-9][A-Za-z0-9.-]*$') { throw 'Invalid SSH target.' }
foreach ($backupArgument in @($backupScript, $Identity, $KnownHosts, $EncryptionKey, $Destination, $DatabaseKey, $DeletionStateDestination, $CheckpointDestination, $CheckpointFingerprint)) {
    if (-not $backupArgument) { continue }
    if ($backupArgument.Contains('"') -or $backupArgument.Contains("`n") -or $backupArgument.Contains("`r")) { throw 'Invalid task argument.' }
}
$backupValues = @($backupScript, '--host', $SshTarget, '--identity', $Identity, '--known-hosts', $KnownHosts, '--key-file', $EncryptionKey, '--destination', $Destination)
if ($DatabaseKey) { $backupValues += @('--database-key-file', $DatabaseKey) }
if ($DeletionStateDestination) { $backupValues += @('--deletion-state-destination', $DeletionStateDestination) }
if ($CheckpointDestination) { $backupValues += @('--checkpoint-destination', $CheckpointDestination, '--checkpoint-fingerprint', $CheckpointFingerprint) }
$backupArguments = ($backupValues | ForEach-Object { '"' + [regex]::Replace($_, '(\\+)$', '$1$1') + '"' }) -join ' '
$backupTaskPython = Join-Path (Split-Path -Parent $Python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $backupTaskPython -PathType Leaf)) { throw 'A matching pythonw.exe is required for a background Windows task.' }
$backupAction = New-ScheduledTaskAction -Execute $backupTaskPython -Argument $backupArguments -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
$backupTrigger = New-ScheduledTaskTrigger -Daily -At '09:00'
$backupSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$backupPrincipal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
# Register only after a successful manual transfer; never disguise an unusable schedule as setup success.
& $Python @backupValues
if ($LASTEXITCODE -ne 0) { throw 'Initial verified backup failed; scheduled task was not registered.' }
Register-ScheduledTask -TaskName 'PolicyLens-Encrypted-Offsite-Backup' -Action $backupAction -Trigger $backupTrigger -Settings $backupSettings -Principal $backupPrincipal -Description 'Verified encrypted PolicyLens snapshots; runs while this Windows user is signed in.' -Force | Select-Object TaskName, State
