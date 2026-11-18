"""C30 (stage s1e) pre-specified analyses, fixed before any C30 run (2026-11-10).

Question: does the C29 protocol (per-session silent calibration + training that includes low duty) remove the misses of
the C27 workload set (C27: frozen diverse model 44/48 hidden, 0/16 false alarms)?  Same 8 cells as C27, new session.
Reuses c28_stats cp/cell/block_acc/signflip/campaign.  Calibration calls ('silent_cal', block -1) never count.
  primary    C29/call_whole_sesscal (frozen 2026-11-06): hidden alerts over the 6 hidden cells (48 runs) and false
             alarms on the 16 test silents; per-cell counts with exact 95% CIs
  secondary  (1) C27_diverse/call_temporal on the same runs (direct replication of the 44/48 detector)
             (2) block sign-flip tests on the 64 test runs: C29 primary vs C27 model; C30 primary vs C29 primary
             (3) C30 models (refit on C24+C27+C28+C29, frozen before C30) and the other C29 representations
             (4) every frozen branch per cell (descriptive)
The C27 44/48 is a different session; the comparison with it is descriptive only.
"""
import csv, json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import c28_stats as S  # noqa: E402
PRIMARY = 'C29/call_whole_sesscal'; C27M = 'C27_diverse/call_temporal'; C30P = 'C30/call_whole_sesscal'
HIDDEN = ['gzip16', 'gzip4_d25', 'gzip6_d37', 'gzip3_d19', 'json8', 'bzip2_r']

def load(d):
    rows = []
    for name in ('predictions.csv', 'predictions_diverse.csv', 'predictions_c29.csv', 'predictions_c30.csv'):
        p = d / name
        if p.exists():
            with p.open(encoding='utf-8') as f:
                rows += list(csv.DictReader(f))
    out = []
    for r in rows:
        if r['condition'] == 'silent_cal':
            continue
        r['alert'] = r['alert'] == 'True'; r['actual_active'] = r['actual_active'] == 'True'
        out.append(r)
    return out

def summary(rows, det):
    cells = {c: S.cell(rows, det, c) for c in HIDDEN + ['silent']}
    k = sum(cells[c]['alerts'] for c in HIDDEN); n = sum(cells[c]['n'] for c in HIDDEN)
    fa = cells['silent']['alerts']; ns = cells['silent']['n']
    return {'hidden_alerts': [k, n], 'hidden_cp95': S.cp(k, n) if n else None, 'silent_false_alarms': [fa, ns],
            'silent_fa_cp95': S.cp(fa, ns) if ns else None, 'correct': [k + ns - fa, n + ns],
            'by_condition': {c: [cells[c]['alerts'], cells[c]['n']] for c in HIDDEN + ['silent']}}

def main(stage='s1e', out_name='c30_stats.json'):
    d = S.campaign(stage); rows = load(d); dets = sorted({r['detector'] for r in rows})
    out = {'campaign': d.name, 'primary': PRIMARY, 'c27_model': C27M, 'c30_primary': C30P,
           'primary_summary': summary(rows, PRIMARY), 'primary_by_condition': {c: S.cell(rows, PRIMARY, c) for c in HIDDEN + ['silent']},
           'reference_c27_session': {'detector': C27M, 'hidden_alerts': [44, 48], 'silent_false_alarms': [0, 16], 'note': 'different session (2026-11-06 s1b); descriptive only'}}
    bt = {}
    for a_det, b_det in ((PRIMARY, C27M), (C30P, PRIMARY)):
        if a_det not in dets or b_det not in dets:
            continue
        a, ka, na = S.block_acc(rows, a_det); b, kb, nb = S.block_acc(rows, b_det)
        ah, kah, nah = S.block_acc(rows, a_det, set(HIDDEN)); bh, kbh, nbh = S.block_acc(rows, b_det, set(HIDDEN))
        bt[a_det + ' vs ' + b_det] = {'all': {'a_correct': [ka, na], 'b_correct': [kb, nb], 'test': S.signflip(a, b)},
                                      'hidden_only': {'a_correct': [kah, nah], 'b_correct': [kbh, nbh], 'test': S.signflip(ah, bh)}}
    out['block_tests'] = bt
    out['all_detectors'] = {det: summary(rows, det) for det in dets}
    S.OUT.mkdir(parents=True, exist_ok=True); (S.OUT / out_name).write_text(json.dumps(out, indent=1), encoding='utf-8')
    for det in [PRIMARY, C27M, C30P, 'C29/call_temporal_sesscal', 'C30/call_temporal_sesscal', 'C29/call_whole_raw']:
        if det in dets:
            s = out['all_detectors'][det]
            print('  %-28s hidden %d/%d  FA %d/%d  correct %d/%d  %s' % (det, *s['hidden_alerts'], *s['silent_false_alarms'], *s['correct'],
                                                                          json.dumps(s['by_condition'])))
    for k, v in bt.items():
        print('  block test', k, json.dumps(v['all']['test']), 'hidden', json.dumps(v['hidden_only']['test']))
    return out

if __name__ == '__main__':
    main(*(sys.argv[1:3]))
