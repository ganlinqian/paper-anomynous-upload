$ErrorActionPreference='Stop'
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
Set-Location -LiteralPath $PSScriptRoot
[IO.Directory]::CreateDirectory((Join-Path $PSScriptRoot 'jobs'))|Out-Null
$ErrorActionPreference='Continue'
& python -u (Join-Path $PSScriptRoot 'collect_burst.py') 1>jobs/collect.stdout.log 2>jobs/collect.stderr.log
$rc=$LASTEXITCODE
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'jobs/collect.exit.json'),('{"returncode":'+$rc+',"utc":"'+[DateTime]::UtcNow.ToString('o')+'"}'))
exit $rc
