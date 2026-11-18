# C37 chain (2026-11-16, session ws_revision; derived from run_sp2027_chain.ps1, which is unchanged):
# [s1z smoke collect] -> power sync (pre) -> s1m collect -> s1n collect -> power sync (post) -> extract/fetch/eval-c31,eval-c35
# for s1m and s1n.  Stops at the first failure.  ToDesk on capture_pc is stopped and kept off (user instruction 2026-11-10).
param([switch]$SkipSmoke, [switch]$SmokeOnly)
$ErrorActionPreference = 'Continue'
Set-Location -LiteralPath $PSScriptRoot
(Get-Process -Id $PID).PriorityClass = 'BelowNormal'
$env:OMP_NUM_THREADS='1'; $env:OPENBLAS_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'; $env:PYTHONUTF8='1'
$py = '<PYTHON>'
$sync = '<WORKSPACE>/ws_revision\results\power_c37\sync_pulses.py'
$jobs = Join-Path $PSScriptRoot 'jobs_c37'; [IO.Directory]::CreateDirectory($jobs) | Out-Null
$chain = Join-Path $jobs 'chain.log'; $utf8 = New-Object System.Text.UTF8Encoding($false)
function Log([string]$m) { [IO.File]::AppendAllText($chain, ([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ') + ' ' + $m + "`r`n"), $utf8) }
function Py([string]$name, [string[]]$argv) {
    $out = Join-Path $jobs ($name + '.stdout.log'); $err = Join-Path $jobs ($name + '.stderr.log')
    $p = Start-Process -FilePath $py -ArgumentList (@('-X', 'utf8', '-u') + $argv) -WorkingDirectory $PSScriptRoot -RedirectStandardOutput $out -RedirectStandardError $err -NoNewWindow -PassThru
    $null = $p.Handle; $p.WaitForExit(); Log ($name + ' rc=' + $p.ExitCode); return $p.ExitCode
}
function Latest([string]$stage) { (Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot ('campaigns\LATEST_' + $stage + '.json')) | ConvertFrom-Json).directory }
function capture_pc([string]$code) {
    $b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($code))
    return (& ssh -o BatchMode=yes -o ConnectTimeout=12 -i '<SSH_KEY>' win@192.0.2.4 ('powershell -NoProfile -NonInteractive -EncodedCommand ' + $b64) 2>&1 | Out-String).Trim()
}
function Post([string]$stage) {
    $c = Latest $stage; $ok = $false
    for ($i = 1; $i -le 4 -and -not $ok; $i++) {
        $null = Py ($stage + '_extract' + $i) @('process_sp2027.py', 'extract', '--campaign', $c, '--budget', '1500')
        $ok = (Py ($stage + '_fetch' + $i) @('process_sp2027.py', 'fetch', '--campaign', $c)) -eq 0
    }
    if (-not $ok) { throw ($stage + ' extraction/fetch failed') }
    foreach ($e in 'eval-c31', 'eval-c35') {
        if ((Py ($stage + '_' + $e) @('process_sp2027.py', $e, '--campaign', $c)) -ne 0) { throw ($stage + ' ' + $e + ' failed') }
    }
}
Log ('chain start skip_smoke=' + $SkipSmoke + ' smoke_only=' + $SmokeOnly + ' pid=' + $PID)
$status = 'complete'
try {
    Log ('todesk stop: ' + (capture_pc 'Stop-Service -Name ToDesk_Service -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 3; Get-Process -Name ToDesk* -ErrorAction SilentlyContinue | Stop-Process -Force; Start-Sleep -Seconds 5; "service=" + (Get-Service ToDesk_Service).Status + " processes=" + @(Get-Process -Name ToDesk* -ErrorAction SilentlyContinue).Count'))
    if (-not $SkipSmoke) {
        Log 'stage s1z collect (smoke)'
        if ((Py 's1z' @('collect_sp2027_c37.py', '--stage', 's1z')) -ne 0) { throw 's1z smoke failed' }
        Log 'stage s1z done'
    }
    if (-not $SmokeOnly) {
        if ((Py 'sync_pre' @($sync, 'c37pre')) -ne 0) { throw 'sync pre failed' }
        foreach ($s in 's1m', 's1n') {
            Log ('stage ' + $s + ' collect')
            if ((Py $s @('collect_sp2027_c37.py', '--stage', $s)) -ne 0) { throw ($s + ' collection failed') }
        }
        if ((Py 'sync_post' @($sync, 'c37post')) -ne 0) { Log 'sync post failed (continuing to post-processing)' }
        foreach ($s in 's1m', 's1n') { Post $s; Log ('stage ' + $s + ' post done') }
    }
} catch { $status = 'stopped: ' + $_.Exception.Message; Log ('chain ' + $status) }
finally {
    Log ('todesk kept off: ' + (capture_pc '"service=" + (Get-Service ToDesk_Service).Status'))
    [IO.File]::WriteAllText((Join-Path $jobs 'chain.exit.json'), ('{"status":"' + $status.Replace('"', "'").Replace('\', '/') + '","utc":"' + [DateTime]::UtcNow.ToString('o') + '"}'), $utf8)
}
