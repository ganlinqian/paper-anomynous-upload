param([ValidateSet('s1','s3','s2train','s2test')][string]$Stage)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
(Get-Process -Id $PID).PriorityClass = 'BelowNormal'
$env:OMP_NUM_THREADS='1'; $env:OPENBLAS_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'; $env:PYTHONUTF8='1'
$py = '<PYTHON>'
$jobs = Join-Path $PSScriptRoot 'jobs'; [IO.Directory]::CreateDirectory($jobs) | Out-Null
$log = Join-Path $jobs ($Stage + '.stdout.log'); $err = Join-Path $jobs ($Stage + '.stderr.log')
$ErrorActionPreference = 'Continue'
switch ($Stage) {
  's1'      { & $py -X utf8 -u (Join-Path $PSScriptRoot 'collect_sp2027_wait.py') --stage s1 1>$log 2>$err }
  's3'      { & $py -X utf8 -u (Join-Path $PSScriptRoot 'collect_sp2027_wait.py') --stage s3 1>$log 2>$err }
  's2train' { & $py -X utf8 -u (Join-Path $PSScriptRoot 'collect_sp2027_order.py') --stage train 1>$log 2>$err }
  's2test'  { & $py -X utf8 -u (Join-Path $PSScriptRoot 'collect_sp2027_order.py') --stage test 1>$log 2>$err }
}
$rc = $LASTEXITCODE
[IO.File]::WriteAllText((Join-Path $jobs ($Stage + '.exit.json')), ('{"returncode":' + $rc + ',"utc":"' + [DateTime]::UtcNow.ToString('o') + '"}'), (New-Object System.Text.UTF8Encoding($false)))
exit $rc
