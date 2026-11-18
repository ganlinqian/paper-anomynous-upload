$ErrorActionPreference='Stop'
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
Set-Location -LiteralPath $PSScriptRoot
$ErrorActionPreference='Continue'
& python -u (Join-Path $PSScriptRoot 'watch_matrix.py') 1>jobs/matrix-watch.stdout.log 2>jobs/matrix-watch.stderr.log
$rc=$LASTEXITCODE
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'jobs/matrix-watch.exit.json'),('{"returncode":'+$rc+',"utc":"'+[DateTime]::UtcNow.ToString('o')+'"}'))
exit $rc
