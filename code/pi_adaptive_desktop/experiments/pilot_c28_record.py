"""Builds pi_pilots/C28_DUTY_PILOT.json from the cut-off pilot: the printed run lines plus the worker private files."""
import hashlib, json, pathlib
B = pathlib.Path(__file__).resolve().parent; tmp = B / 'pi_pilots' / 'c28_tmp'
runs = [json.loads(l) for l in (B / 'jobs' / 'c28_pilot.stdout.log').read_text(encoding='utf-8').splitlines() if l.startswith('{')]
priv = {}
for q in sorted(tmp.glob('*.private.json')):
    x = json.loads(q.read_text()); priv[q.name.split('.')[0]] = x
cfgs = {q.name.split('.')[0]: json.loads(q.read_text()) for q in sorted(tmp.glob('q*.json')) if not q.name.endswith('.private.json')}
rec = {'note': ('Pilot (no RF) of the unchanged pi_api_sp2027_wait.py on the C28 throttled conditions under campaign CPU settings. '
                'The desktop process was terminated by the project bridge after 7 of 12 planned runs (06:45:09-06:46:10 UTC), so its '
                'finally-block did not run: the Pi lock was released by the closed SSH session; the CPU governor was restored and the '
                "pilot directory removed by pilot_c28_cleanup.py. Acceptance rule fixed before running: valid, inside the wait, archive "
                'matches input, margin to the gateway reply >= 1.0 s.'),
       'planned_runs': 12, 'completed_runs': len(runs), 'runs': runs,
       'accepted_completed_runs': all(r['rc'] == 0 and r['response_ok'] and r['inside_wait'] and r['archive_ok'] and r['margin_s'] >= 1.0 for r in runs),
       'every_condition_once': sorted({r['cond'] for r in runs}),
       'worker_private': priv, 'worker_configs': cfgs,
       'pilot_script_sha256': hashlib.sha256((B / 'pilot_c28.py').read_bytes()).hexdigest(),
       'worker_sha256': hashlib.sha256((B / 'pi_api_sp2027_wait.py').read_bytes()).hexdigest()}
(B / 'pi_pilots' / 'C28_DUTY_PILOT.json').write_text(json.dumps(rec, indent=1), encoding='utf-8')
print(json.dumps({k: rec[k] for k in ('planned_runs', 'completed_runs', 'accepted_completed_runs', 'every_condition_once')}),
      'private files', len(priv), 'configs', len(cfgs))
