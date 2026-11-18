$ErrorActionPreference='Stop'
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
Set-Location -LiteralPath $PSScriptRoot
$ErrorActionPreference='Continue'
& python -u (Join-Path $PSScriptRoot 'transfer_extensions.py') 1>jobs/extension-transfer.stdout.log 2>jobs/extension-transfer.stderr.log
$rc=$LASTEXITCODE
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'jobs/extension-transfer.exit.json'),('{"returncode":'+$rc+',"utc":"'+[DateTime]::UtcNow.ToString('o')+'"}'))
exit $rc
