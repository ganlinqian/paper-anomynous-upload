"""Read-only Pi/thermal pre-run check for the sp2027 supplements (no changes on the Pi)."""
import json, pathlib, sys
SRC = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
sys.path.insert(0, str(SRC / 'burst_study'))
from bridge_utils import connect, run, snapshot, thermal  # noqa: E402
p = connect('192.0.2.60', 'admin', 522)
out = {'snapshot': snapshot(p), 'thermal': thermal()}
out['busy'] = run(p, "pgrep -af '^(perf|strace|resident_tool|python3.*telltale)' || true")['stdout']
out['lock'] = run(p, 'ls -l /home/pi/telltale_g1_20261026/controller.lock 2>&1 || true', check=False)['stdout']
out['load'] = run(p, 'uptime; nproc; free -m | head -2')['stdout']
out['top'] = run(p, 'ps -eo pid,pcpu,pmem,etime,comm --sort=-pcpu | head -8')['stdout']
out['gateway'] = run(p, "pgrep -af 'openclaw' || true")['stdout']
out['sp2027_dirs'] = run(p, 'ls /home/pi/telltale_sp2027 2>/dev/null | tail -5; df -h /home /dev/shm | tail -2')['stdout']
p.close()
print(json.dumps(out, indent=1, ensure_ascii=False))
