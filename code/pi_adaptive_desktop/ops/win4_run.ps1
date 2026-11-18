# Runs a PowerShell script file on capture-pc over ssh (key auth) using -EncodedCommand.
param([Parameter(Mandatory)][string]$Script)
$code = [IO.File]::ReadAllText($Script)
$b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($code))
& ssh -o BatchMode=yes -o ConnectTimeout=12 -i '<SSH_KEY>' win@192.0.2.4 ('powershell -NoProfile -NonInteractive -EncodedCommand ' + $b64)
'ssh_exit=' + $LASTEXITCODE
