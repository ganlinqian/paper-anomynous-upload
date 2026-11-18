$ErrorActionPreference = 'Continue'
Set-Location '<WORKSPACE>/ws_main\results\sp2027\desktop_em'
$env:PYTHONUTF8 = '1'
$py = (Get-Command python).Source
"start $(Get-Date -Format o) python=$py" | Out-File probe_run.log -Encoding utf8
& $py -I probe_sweep.py --out sweep_20261106 --order 'i,m,i,c,i,m,i,c,i' *>> probe_run.log
"exit $LASTEXITCODE $(Get-Date -Format o)" | Out-File probe_run.log -Append -Encoding utf8
