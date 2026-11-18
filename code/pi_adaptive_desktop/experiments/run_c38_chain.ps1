# C38 chain (2026-11-17, session ws_revision; derived from run_c37_chain.ps1, which is unchanged). No power meter.
# s1o collect -> extract/fetch/eval-c31,eval-c35 + envelope features (s1o) -> train C38 (s1k + s1m + s1o) -> s1p collect
# -> extract/fetch/eval-c31,eval-c35 + envelope features + eval C38 (s1p) -> analyze_c38.py.  Stops at the first failure.
param([switch]$SkipS1o)
$ErrorActionPreference = 'Continue'
Set-Location -LiteralPath $PSScriptRoot
(Get-Process -Id $PID).PriorityClass = 'BelowNormal'
$env:OMP_NUM_THREADS='1'; $env:OPENBLAS_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'; $env:PYTHONUTF8='1'
$py = '<PYTHON>'
$ana = '<WORKSPACE>/ws_revision\results\c38\analyze_c38.py'
$model = Join-Path $PSScriptRoot 'models\C38_ENV_MODELS.json'
$jobs = Join-Path $PSScriptRoot 'jobs_c38'; [IO.Directory]::CreateDirectory($jobs) | Out-Null
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
    if ((Py ($stage + '_envrun') @('c38_env.py', 'envrun', '--campaign', $c)) -ne 0) { throw ($stage + ' envelope extraction failed') }
}
Log ('chain start skip_s1o=' + $SkipS1o + ' pid=' + $PID)
$status = 'complete'
try {
    Log ('todesk stop: ' + (capture_pc 'Stop-Service -Name ToDesk_Service -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 3; Get-Process -Name ToDesk* -ErrorAction SilentlyContinue | Stop-Process -Force; Start-Sleep -Seconds 5; "service=" + (Get-Service ToDesk_Service).Status + " processes=" + @(Get-Process -Name ToDesk* -ErrorAction SilentlyContinue).Count'))
    if (-not $SkipS1o) {
        Log 'stage s1o collect'
        if ((Py 's1o' @('collect_sp2027_c38.py', '--stage', 's1o')) -ne 0) { throw 's1o collection failed' }
        Post 's1o'; Log 'stage s1o post done'
    }
    if (-not (Test-Path $model)) {
        $tr = @('c38_env.py', 'train', '--out', $model, '--campaign', (Latest 's1k'), '--campaign', (Latest 's1m'), '--campaign', (Latest 's1o'))
        if ((Py 'train_c38' $tr) -ne 0) { throw 'C38 training failed' }
    }
    Log ('C38 model sha256 ' + (Get-FileHash -Algorithm SHA256 $model).Hash.ToLower())
    Log 'stage s1p collect'
    if ((Py 's1p' @('collect_sp2027_c38.py', '--stage', 's1p')) -ne 0) { throw 's1p collection failed' }
    Post 's1p'
    if ((Py 's1p_eval-c38' @('c38_env.py', 'eval', '--model', $model, '--campaign', (Latest 's1p'))) -ne 0) { throw 's1p eval-c38 failed' }
    Log 'stage s1p post done'
    if ((Py 'analyze_c38' @($ana)) -ne 0) { throw 'analyze_c38 failed' }
} catch { $status = 'stopped: ' + $_.Exception.Message; Log ('chain ' + $status) }
finally {
    Log ('todesk kept off: ' + (capture_pc '"service=" + (Get-Service ToDesk_Service).Status'))
    [IO.File]::WriteAllText((Join-Path $jobs 'chain.exit.json'), ('{"status":"' + $status.Replace('"', "'").Replace('\', '/') + '","utc":"' + [DateTime]::UtcNow.ToString('o') + '"}'), $utf8)
}
