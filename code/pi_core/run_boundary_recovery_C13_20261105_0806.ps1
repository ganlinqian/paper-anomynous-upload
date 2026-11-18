$ErrorActionPreference='Stop'
$projectRoot='<WORKSPACE>/ws_pi'
Set-Location $projectRoot
(Get-Process -Id $PID).PriorityClass='BelowNormal'
$env:PYTHONUTF8='1'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
$jobPath=Join-Path $projectRoot 'results/scenario_rf_20261104/jobs/boundary_recovery_C13_20261105_0806'
[IO.Directory]::CreateDirectory($jobPath) | Out-Null
$pythonPath='<PYTHON>'
& $pythonPath -X utf8 -u 'results/scenario_rf_20261104/resume_boundary_processing_20261105_0806.py' --dataset 'C13' 1> (Join-Path $jobPath 'stdout.log') 2> (Join-Path $jobPath 'stderr.log')
$taskExit=$LASTEXITCODE
$exitRecord=@{returncode=$taskExit;utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Compress
[IO.File]::WriteAllText((Join-Path $jobPath 'exit.json'),$exitRecord,(New-Object System.Text.UTF8Encoding($false)))
exit $taskExit
