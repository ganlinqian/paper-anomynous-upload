$ErrorActionPreference='Stop'
Set-Location '<WORKSPACE>/ws_pi'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:PYTHONUTF8='1'
$env:MKL_NUM_THREADS='1'
python -u results/scenario_rf_20261104/watch_early_confirmations.py 1> results/scenario_rf_20261104/jobs/early-confirmations.stdout.log 2> results/scenario_rf_20261104/jobs/early-confirmations.stderr.log
$rc=$LASTEXITCODE
@{returncode=$rc;utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Compress | Set-Content results/scenario_rf_20261104/jobs/early-confirmations.exit.json -Encoding UTF8
exit $rc
