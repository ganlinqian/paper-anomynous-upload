"""Cleanup after the C28 pilot was cut off by the bridge (its finally-block never ran): inspect the Pi, restore the CPU
settings recorded by bench_status.py at 06:43:49 UTC (ondemand / 600000 / 1800000), remove only the pilot's own
directory, and report.  Usage: python pilot_c28_cleanup.py [--apply]"""
import json, pathlib, sys
SRC = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
sys.path.insert(0, str(SRC / 'burst_study')); from bridge_utils import *   # noqa
apply = '--apply' in sys.argv
p = connect('192.0.2.60', 'admin', 522); out = {'utc': stamp(), 'apply': apply}
try:
    out['state_before'] = snapshot(p).splitlines()[:5]
    out['lock'] = run(p, 'cat /home/pi/telltale_g1_20261026/controller.lock 2>&1 || true')['stdout'].strip()
    out['procs'] = run(p, "pgrep -af 'pi_wait.py|sp2027_c28pilot|gzip -n' | grep -v pgrep || true")['stdout'].strip()
    out['pilot_dirs'] = run(p, 'ls -d /home/pi/telltale_sp2027/sp2027_c28pilot_* 2>/dev/null || true')['stdout'].split()
    if apply:
        assert not out['procs'], 'pilot processes still running'
        lk = out['lock']
        if lk.startswith('sp2027_c28pilot_'):
            out['lock_removed'] = run(p, 'rm -f /home/pi/telltale_g1_20261026/controller.lock')['rc']
        out['restore'] = run(p, "sudo -n sh -c 'echo 1800000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq; echo 600000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq; echo ondemand > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'", check=False)['rc']
        for x in out['pilot_dirs']:
            assert x.startswith('/home/pi/telltale_sp2027/sp2027_c28pilot_')
            out.setdefault('removed', []).append([x, run(p, 'rm -rf ' + x, check=False)['rc']])
        out['state_after'] = snapshot(p).splitlines()[:5]
        out['lock_after'] = run(p, 'ls -l /home/pi/telltale_g1_20261026/controller.lock 2>&1 || true')['stdout'].strip()
    out['thermal'] = thermal()
finally:
    p.close()
tmp = pathlib.Path(__file__).resolve().parent / 'pi_pilots' / 'c28_tmp'
if apply and tmp.exists():
    for q in tmp.glob('*'):
        q.unlink()
    tmp.rmdir(); out['local_tmp_removed'] = True
print(json.dumps(out, indent=1))
