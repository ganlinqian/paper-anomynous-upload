"""C29 (stage s1d) pre-specified analyses, fixed before any C29 run (2026-11-06).

Thin wrapper over c28_stats: reuses its cp/cell/block_acc/signflip/campaign.  Calibration calls (condition
'silent_cal', block -1) are dropped from every test count.  Endpoints are fixed in 03_.md C29 section:
  primary    C29/call_whole_sesscal alerts per hidden condition (n=8) and false alarms on the 16 test silent runs
  secondary  (1) the other two C29 models and every frozen branch per condition
             (2) block sign-flip test vs the C28 primary (frozen C27 C27_diverse/call_temporal) and vs the
                 single-workload C10_transfer/temporal_260/plain on the same 64 test runs
             (3) low-and-slow paired exact McNemar at 6.25% and 3.125%
             (4) frontier = lowest tested duty with >= 6/8 primary alerts (fixed-span and stretched separately)
"""
import csv, json, pathlib, sys
from scipy.stats import binom
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import c28_stats as S  # noqa: E402
PRIMARY = 'C29/call_whole_sesscal'; C28P = 'C27_diverse/call_temporal'; SINGLE = 'C10_transfer/temporal_260/plain'
SPEC = {'gzip3_d19': (0.1875, 3.0, 'fixed'), 'gzip2_d12': (0.125, 2.0, 'fixed'), 'gzip1_d06': (0.0625, 1.0, 'fixed'),
        'gzip05_d03': (0.03125, 0.5, 'fixed'), 'gzip2_d06': (0.0625, 2.0, 'stretched'), 'gzip1_d03': (0.03125, 1.0, 'stretched')}
PAIRS = [('gzip2_d06', 'gzip1_d06'), ('gzip1_d03', 'gzip05_d03')]

def load(d):
    rows = []
    for name in ('predictions.csv', 'predictions_diverse.csv', 'predictions_c29.csv'):
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

def main(stage='s1d', out_name='c29_stats.json'):
    d = S.campaign(stage); rows = load(d)
    out = {'campaign': d.name, 'primary': PRIMARY, 'c28_primary': C28P, 'single_workload': SINGLE,
           'primary_by_condition': {c: S.cell(rows, PRIMARY, c) for c in SPEC},
           'primary_silent_false_alarms': S.cell(rows, PRIMARY, 'silent')}
    bt = {}
    for other in (C28P, SINGLE):
        a, ka, na = S.block_acc(rows, PRIMARY); b, kb, nb = S.block_acc(rows, other)
        ah, kah, nah = S.block_acc(rows, PRIMARY, set(SPEC)); bh, kbh, nbh = S.block_acc(rows, other, set(SPEC))
        bt[other] = {'all': {'primary_correct': [ka, na], 'other_correct': [kb, nb], 'test': S.signflip(a, b)},
                     'hidden_only': {'primary_correct': [kah, nah], 'other_correct': [kbh, nbh], 'test': S.signflip(ah, bh)}}
    out['block_tests'] = bt
    ls = {}
    for st, fx in PAIRS:
        a = S.cell(rows, PRIMARY, st)['by_block']; b = S.cell(rows, PRIMARY, fx)['by_block']
        ks = sorted(set(a) & set(b)); so = sum(a[k] and not b[k] for k in ks); fo = sum(b[k] and not a[k] for k in ks)
        ls[st + ' vs ' + fx] = {'stretched_alerts': sum(a[k] for k in ks), 'fixed_alerts': sum(b[k] for k in ks),
                                'stretched_only': so, 'fixed_only': fo, 'p_one_sided': float(binom.sf(so - 1, so + fo, .5)) if so + fo else 1.0}
    out['low_and_slow'] = ls
    fr = {}
    for span in ('fixed', 'stretched'):
        duties = sorted((SPEC[c][0], c) for c in SPEC if SPEC[c][2] == span)
        hit = [d for d, c in duties if out['primary_by_condition'][c]['alerts'] >= 6]
        fr[span] = {'lowest_duty_detected_6of8': min(hit) if hit else None}
    out['frontier'] = fr
    dets = sorted({r['detector'] for r in rows})
    out['all_detectors'] = {det: {c: [S.cell(rows, det, c)['alerts'], S.cell(rows, det, c)['n']] for c in list(SPEC) + ['silent']} for det in dets}
    S.OUT.mkdir(parents=True, exist_ok=True); (S.OUT / out_name).write_text(json.dumps(out, indent=1), encoding='utf-8')
    pc = out['primary_by_condition']
    for c in SPEC:
        print('  %-11s duty %6.3f%% %-9s primary %d/%d CI %s' % (c, 100 * SPEC[c][0], SPEC[c][2], pc[c]['alerts'], pc[c]['n'], pc[c]['cp95']))
    print('  silent FA', out['primary_silent_false_alarms']['alerts'], '/', out['primary_silent_false_alarms']['n'])
    print('  frontier', json.dumps(fr)); print('  low-and-slow', json.dumps(ls))
    for o, v in bt.items():
        print('  vs', o, 'hidden_only', json.dumps(v['hidden_only']['test']))
    return out

if __name__ == '__main__':
    main(*(sys.argv[1:3]))
