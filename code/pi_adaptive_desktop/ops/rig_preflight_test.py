"""Dry preflight of rig_capture_stagger_sp2027.py on capture-pc: start, read the preflight receipt, stop. No capture."""
import json, pathlib, sys, time
SRC = pathlib.Path(r'<WORKSPACE>/ws_pi\results\scenario_rf_20261104')
sys.path.insert(0, str(SRC / 'burst_study')); sys.path.insert(1, str(SRC))
from bridge_utils import connect  # noqa: E402
from collect import Rig           # noqa: E402
RIG = pathlib.Path(r'<WORKSPACE>/ws_main\results\sp2027\experiments\rig_capture_stagger_sp2027.py')
tag = 'preflighttest' + time.strftime('%Y%m%d%H%M%S', time.gmtime())
w = connect('192.0.2.4', 'win'); wf = w.open_sftp()
try:
    wf.mkdir('<DATA>/telltale_sp2027')
except OSError:
    pass
rs = '<DATA>/telltale_sp2027/rig_' + tag + '.py'; root = '<DATA>/telltale_sp2027/' + tag
wf.put(str(RIG), rs)
out = {}
try:
    rig = Rig(w, rs, root, tag)
    pre = rig.pre['preflight']
    out['preflight'] = {k: pre.get(k) for k in ('bus', 'free', 'console_user', 'other_workloads', 'cpu_load', 'remote_tools', 'query_user')}
    out['hackrf_listed'] = all(s in pre.get('hackrf_info', '') for s in ('930c64dc2b4590c3', '16bc62dc2e3196a7'))
    out['stop'] = rig.stop()
except Exception as ex:
    out['error'] = str(ex)[-1500:]
finally:
    for path in (rs,):
        try:
            wf.remove(path)
        except OSError:
            pass
    try:
        wf.rmdir(root)
    except OSError as ex:
        out['rmdir'] = str(ex)
    wf.close(); w.close()
print(json.dumps(out, indent=1, ensure_ascii=False))
