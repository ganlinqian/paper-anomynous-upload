$ErrorActionPreference='Stop'
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
Set-Location -LiteralPath $PSScriptRoot
$ErrorActionPreference='Continue'
& python -u (Join-Path $PSScriptRoot 'validate_wait.py') 1>jobs/validate-wait.stdout.log 2>jobs/validate-wait.stderr.log
$rc=$LASTEXITCODE
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'jobs/validate-wait.exit.json'),('{"returncode":'+$rc+',"utc":"'+[DateTime]::UtcNow.ToString('o')+'"}'))
exit $rc
