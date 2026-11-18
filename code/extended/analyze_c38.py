"""C38 analysis, implementing C38_PREREG.md (experiments dir) exactly; written and hashed (ANALYSIS_FREEZE.json) before
any s1p run.  No fitting.  Inputs: LATEST_s1p / LATEST_s1o campaigns (RESULTS.json, predictions_c35.csv,
predictions_c31.csv, predictions_c38.csv [s1p]).  Outputs c38_results.json / c38_results.md in this folder."""
import csv, datetime, json, pathlib, sys
from scipy.stats import beta, binomtest
sys.stdout.reconfigure(encoding='utf-8')
ROOT = pathlib.Path(__file__).resolve().parents[2]
H = ROOT / 'data/extended/c38'
OUT = ROOT / 'outputs/c38'
OUT.mkdir(parents=True, exist_ok=True)
EXP = ROOT / 'data/pi_adaptive_desktop/experiments'
D1, D2 = 'C35/self_roll4_p70', 'C31/avg_whole_temporal'
PERSIST_SEEN, PERSIST_UNSEEN = ('persist12', 'persist25'), ('persist09', 'persist12s')
HIDDEN = ('gzip16', 'gzip3_d19', 'sha32')


def latest(stage):
    return EXP / 'campaigns' / json.loads((EXP / 'campaigns' / ('LATEST_' + stage + '.json')).read_text(encoding='utf-8-sig'))['campaign']


def cp(k, n):
    return [round(float(beta.ppf(.025, k, n - k + 1)), 3) if k else 0.0, round(float(beta.ppf(.975, k + 1, n - k)), 3) if k < n else 1.0]


def load(d, c38):
    rows = [x for x in json.loads((d / 'RESULTS.json').read_text(encoding='utf-8-sig')) if x['condition'] != 'silent_cal']
    A = {}
    for fn in ('predictions_c35.csv', 'predictions_c31.csv') + (('predictions_c38.csv',) if c38 else ()):
        for r in csv.DictReader(open(d / fn, encoding='utf-8')):
            if fn == 'predictions_c38.csv':
                A[(r['detector'] + '_p50', r['id'])] = r['alert_p50'] == 'True'; A[(r['detector'] + '_p70', r['id'])] = r['alert_p70'] == 'True'
            elif r['detector'] in (D1, D2):
                A[(r['detector'], r['id'])] = r['alert'] == 'True'
    return rows, A


def table(rows, A, dets):
    groups = {'persist_seen': lambda x: x['condition'] in PERSIST_SEEN, 'persist_unseen': lambda x: x['condition'] in PERSIST_UNSEEN,
              'persist_all': lambda x: x['condition'].startswith('persist'), 'false_alarm_negatives': lambda x: x['condition'] in ('silent', 'bg_log'),
              'hidden_ordinary': lambda x: x['condition'] in HIDDEN}
    out = {}
    for g, f in list(groups.items()) + [(c, (lambda c: lambda x: x['condition'] == c)(c)) for c in sorted({x['condition'] for x in rows})]:
        sel = [x for x in rows if f(x)]
        if not sel: continue
        out[g] = {}
        for det in dets:
            k = sum(alert(A, det, x) for x in sel); out[g][det] = {'k': k, 'n': len(sel), 'CI95': cp(k, len(sel))}
    return out


def alert(A, det, x):
    if det == 'D1|C38':
        return A[(D1, x['id'])] or A[('C38/roll4_p50', x['id'])]
    return A[(det, x['id'])]


def main():
    out = {'utc': datetime.datetime.utcnow().isoformat() + 'Z'}
    d = latest('s1p'); rows, A = load(d, True)
    dets = ['C38/roll4_p50', D1, D2, 'D1|C38', 'C38/roll4_p70', 'C38/cal_p50', 'C38/roll4_admit_p50']
    t = table(rows, A, dets); out['s1p'] = {'campaign': d.name, 'n_test': len(rows), 'table': t}
    pr = [x for x in rows if x['condition'].startswith('persist')]
    a_only = sum(alert(A, 'C38/roll4_p50', x) and not alert(A, D1, x) for x in pr); b_only = sum(alert(A, D1, x) and not alert(A, 'C38/roll4_p50', x) for x in pr)
    out['s1p']['mcnemar_persist_C38_vs_D1'] = {'C38_only': a_only, 'D1_only': b_only, 'p': binomtest(a_only, a_only + b_only).pvalue if a_only + b_only else 1.0}
    pk = t['persist_all']['C38/roll4_p50']['k']; fk = t['false_alarm_negatives']['C38/roll4_p50']['k']
    out['s1p']['success_criterion'] = {'persist_detected': pk, 'persist_n': t['persist_all']['C38/roll4_p50']['n'], 'false_alarms': fk,
                                       'fa_n': t['false_alarm_negatives']['C38/roll4_p50']['n'], 'met': bool(pk >= 24 and fk <= 3)}
    try:
        d0 = latest('s1o'); r0, A0 = load(d0, False); out['s1o_frozen_D1_D2'] = {'campaign': d0.name, 'n_test': len(r0), 'table': table(r0, A0, [D1, D2])}
    except FileNotFoundError as e:
        out['s1o_frozen_D1_D2'] = {'error': repr(e)}
    (OUT / 'c38_results.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    order = ['persist_all', 'persist_seen', 'persist_unseen', 'persist12', 'persist25', 'persist09', 'persist12s', 'false_alarm_negatives', 'silent', 'bg_log',
             'hidden_ordinary', 'gzip16', 'gzip3_d19', 'sha32']
    L = ['# C38 s1p results (alerts / runs)', '', '| group | ' + ' | '.join(dets) + ' |', '|' + '---|' * (len(dets) + 1)]
    L += ['| %s | %s |' % (g, ' | '.join('%d/%d' % (t[g][k]['k'], t[g][k]['n']) for k in dets)) for g in order if g in t]
    L += ['', 'McNemar persist C38 vs D1: ' + json.dumps(out['s1p']['mcnemar_persist_C38_vs_D1']), 'Success criterion: ' + json.dumps(out['s1p']['success_criterion'])]
    if 'table' in out['s1o_frozen_D1_D2']:
        t0 = out['s1o_frozen_D1_D2']['table']; L += ['', '## s1o (training session for C38; independent test for frozen D1/D2)', '', '| group | D1 | D2 |', '|---|---|---|']
        L += ['| %s | %d/%d | %d/%d |' % (g, t0[g][D1]['k'], t0[g][D1]['n'], t0[g][D2]['k'], t0[g][D2]['n']) for g in sorted(t0)]
    (OUT / 'c38_results.md').write_text('\n'.join(L) + '\n', encoding='utf-8'); print('\n'.join(L))


if __name__ == '__main__':
    main()
