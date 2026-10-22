param(
    [Parameter(Mandatory)][string]$Python,
    [Parameter(Mandatory)][string]$SshTarget,
    [Parameter(Mandatory)][string]$Identity,
    [Parameter(Mandatory)][string]$KnownHosts,
    [Parameter(Mandatory)][string]$EncryptionKey,
    [Parameter(Mandatory)][string]$Destination
)
$ErrorActionPreference = 'Stop'
$backupScript = Join-Path $PSScriptRoot 'pull_backup.py'
$backupPaths = @($Python, $backupScript, $Identity, $KnownHosts, $EncryptionKey)
foreach ($backupPath in $backupPaths) {
    if (-not (Test-Path -LiteralPath $backupPath -PathType Leaf)) { throw "Required backup file is unavailable: $backupPath" }
}
if ($SshTarget -notmatch '^[A-Za-z_][A-Za-z0-9_-]*@[A-Za-z0-9][A-Za-z0-9.-]*$') { throw 'Invalid SSH target.' }
foreach ($backupArgument in @($backupScript, $Identity, $KnownHosts, $EncryptionKey, $Destination)) {
    if ($backupArgument.Contains('"') -or $backupArgument.Contains("`n") -or $backupArgument.Contains("`r")) { throw 'Invalid task argument.' }
}
$backupValues = @($backupScript, '--host', $SshTarget, '--identity', $Identity, '--known-hosts', $KnownHosts, '--key-file', $EncryptionKey, '--destination', $Destination)
$backupArguments = ($backupValues | ForEach-Object { '"' + [regex]::Replace($_, '(\\+)$', '$1$1') + '"' }) -join ' '
$backupAction = New-ScheduledTaskAction -Execute (Resolve-Path -LiteralPath $Python).Path -Argument $backupArguments
$backupTrigger = New-ScheduledTaskTrigger -Daily -At '09:00'
$backupSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$backupPrincipal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
# Register only after a successful manual transfer; never disguise an unusable schedule as setup success.
& $Python $backupScript --host $SshTarget --identity $Identity --known-hosts $KnownHosts --key-file $EncryptionKey --destination $Destination
if ($LASTEXITCODE -ne 0) { throw 'Initial verified backup failed; scheduled task was not registered.' }
Register-ScheduledTask -TaskName 'PolicyLens-Encrypted-Offsite-Backup' -Action $backupAction -Trigger $backupTrigger -Settings $backupSettings -Principal $backupPrincipal -Description 'Verified encrypted PolicyLens snapshots; runs while this Windows user is signed in.' -Force | Select-Object TaskName, State
