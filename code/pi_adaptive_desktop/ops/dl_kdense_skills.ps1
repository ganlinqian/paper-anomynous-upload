# Background download of the public K-Dense-AI/scientific-agent-skills source archive (anonymous GET, no git).
# Runs as a scheduled task because the archive takes longer than one project-bridge exec.
param([string]$Out = '<WORKSPACE>/ws_main\third_party\scientific-agent-skills\download\scientific-agent-skills-main.zip')
$log = [IO.Path]::ChangeExtension($Out, '.log')
"start $(Get-Date -Format o)" | Set-Content $log
& curl.exe -fL --retry 3 --retry-delay 10 --max-time 1500 --speed-limit 2000 --speed-time 180 -sS https://codeload.github.com/K-Dense-AI/scientific-agent-skills/zip/refs/heads/main -o $Out 2>> $log
"curl_rc=$LASTEXITCODE end $(Get-Date -Format o)" | Add-Content $log
if (Test-Path $Out) { "bytes=$((Get-Item $Out).Length) sha256=$((Get-FileHash $Out -Algorithm SHA256).Hash)" | Add-Content $log }
"done" | Add-Content $log
