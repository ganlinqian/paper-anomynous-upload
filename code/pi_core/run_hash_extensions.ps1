$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
$ErrorActionPreference='Continue'
& python -u (Join-Path $PSScriptRoot 'hash_extensions.py') 1>jobs/extension-hash.stdout.log 2>jobs/extension-hash.stderr.log
$rc=$LASTEXITCODE
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'jobs/extension-hash.exit.json'),('{"returncode":'+$rc+',"utc":"'+[DateTime]::UtcNow.ToString('o')+'"}'))
exit $rc
