$ErrorActionPreference='Stop'
Set-Location '<WORKSPACE>/ws_pi'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
python -u results/scenario_rf_20261104/burst_confirmation_study/after_confirmation.py 1> results/scenario_rf_20261104/jobs/burst-confirmation-resume.stdout.log 2> results/scenario_rf_20261104/jobs/burst-confirmation-resume.stderr.log
$rc=$LASTEXITCODE
@{returncode=$rc;utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Compress | Set-Content results/scenario_rf_20261104/jobs/burst-confirmation-resume.exit.json -Encoding UTF8
exit $rc
