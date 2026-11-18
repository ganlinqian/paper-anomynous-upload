param([ValidateSet('positive','matrix','boundary')][string]$Stage)
$ErrorActionPreference='Stop'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
Set-Location -LiteralPath $PSScriptRoot
$jobDir=Join-Path $PSScriptRoot 'jobs'
[IO.Directory]::CreateDirectory($jobDir)|Out-Null
$log=Join-Path $jobDir ($Stage+'.stdout.log')
$err=Join-Path $jobDir ($Stage+'.stderr.log')
$ErrorActionPreference='Continue'
& python -u (Join-Path $PSScriptRoot 'collect.py') --stage $Stage 1>$log 2>$err
$rc=$LASTEXITCODE
$ErrorActionPreference='Stop'
[IO.File]::WriteAllText((Join-Path $jobDir ($Stage+'.exit.json')),('{"returncode":'+$rc+',"utc":"'+[DateTime]::UtcNow.ToString('o')+'"}'))
exit $rc
