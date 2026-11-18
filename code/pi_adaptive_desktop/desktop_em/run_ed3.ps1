param([string]$Batch = 'd2', [int]$Blocks = 10, [int]$Seed = 31)
$ErrorActionPreference = 'Continue'
Set-Location '<WORKSPACE>/ws_main\results\sp2027\desktop_em'
$env:PYTHONUTF8 = '1'
$py = (Get-Command python).Source
$log = "ed3_$Batch.log"
"start $(Get-Date -Format o) batch=$Batch blocks=$Blocks seed=$Seed" | Out-File $log -Encoding utf8
& $py -I desktop_witness_d2.py --batch $Batch --blocks $Blocks --seed $Seed --lo 1.38e9 --hidden tar1024 --contracts mixed --out runs 2>&1 | Out-File $log -Append -Encoding utf8
"exit $LASTEXITCODE $(Get-Date -Format o)" | Out-File $log -Append -Encoding utf8
