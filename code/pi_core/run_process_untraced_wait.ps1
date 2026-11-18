$ErrorActionPreference = 'Stop'
$projectRoot = '<WORKSPACE>/ws_pi'
Set-Location $projectRoot
(Get-Process -Id $PID).PriorityClass = 'BelowNormal'
$env:OMP_NUM_THREADS='1'
$env:PYTHONUTF8='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
$pythonPath='<PYTHON>'
& $pythonPath -u 'results/scenario_rf_20261104/process_untraced_wait.py' 1> 'results/scenario_rf_20261104/jobs/process-untraced-wait.stdout.log' 2> 'results/scenario_rf_20261104/jobs/process-untraced-wait.stderr.log'
$taskExit=$LASTEXITCODE
$exitRecord=@{returncode=$taskExit;utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Compress
[IO.File]::WriteAllText((Join-Path $projectRoot 'results/scenario_rf_20261104/jobs/process-untraced-wait.exit.json'),$exitRecord,(New-Object System.Text.UTF8Encoding($false)))
exit $taskExit
