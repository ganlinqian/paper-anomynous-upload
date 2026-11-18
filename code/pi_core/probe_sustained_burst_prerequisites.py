from pathlib import Path
import base64,json,sys
B=Path(__file__).resolve().parent;sys.path.insert(0,str(B/'burst_study'))
from bridge_utils import connect,run,guard
w=connect('192.0.2.4','win');p=connect('192.0.2.60','admin',522)
try:
 script="$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);$proc=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -match '^(python|pythonw|hackrf_transfer).*'}|Select-Object ProcessId,CommandLine);[PSCustomObject]@{F_free=[IO.DriveInfo]::new('F').AvailableFreeSpace;J_free=[IO.DriveInfo]::new('J').AvailableFreeSpace;workloads=$proc}|ConvertTo-Json -Depth 4 -Compress"
 command='powershell -NoProfile -NonInteractive -EncodedCommand '+base64.b64encode(script.encode('utf-16le')).decode();z=run(w,command,timeout=25);info=json.loads(z['stdout'])
 state=guard(p);out={'capture-pc':info,'pi_guard':state,'C13_hash_complete':json.loads((B/'untraced_processing_20261105/F/HASH_COMPLETE.json').read_text(encoding='utf-8-sig')),'main_F_complete':json.loads((B/'confirmation_processing_20261105/F_UPLOAD_COMPLETE.json').read_text(encoding='utf-8-sig')),'main_status':json.loads((B/'confirmation_processing_20261105/STATUS.json').read_text(encoding='utf-8-sig'))}
 print(json.dumps(out))
finally:w.close();p.close()
