$ErrorActionPreference='Stop'
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
Set-Location -LiteralPath $PSScriptRoot
$ErrorActionPreference='Continue'
& python -u (Join-Path $PSScriptRoot 'finish_first.py') 1>jobs/finish-first.stdout.log 2>jobs/finish-first.stderr.log
$rc=$LASTEXITCODE
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'jobs/finish-first.exit.json'),('{"returncode":'+$rc+',"utc":"'+[DateTime]::UtcNow.ToString('o')+'"}'))
exit $rc
