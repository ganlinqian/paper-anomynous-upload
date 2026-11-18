"""C37 analysis, implementing C37_PREREG.md (experiments dir) exactly; written before any C37 feature or power file was
read and hashed into ANALYSIS_FREEZE.json.  No fitting.  Inputs: campaigns LATEST_s1m / LATEST_s1n (RESULTS.json,
features/*_930c.npz, predictions_c35.csv, predictions_c31.csv) and, if present, c37_timemap.json + the local power CSV.
Outputs c37_results.json and c37_results.md in this folder."""
import csv, datetime, json, pathlib, sys
import numpy as np
from scipy.stats import beta, binomtest
sys.stdout.reconfigure(encoding='utf-8')
ROOT = pathlib.Path(__file__).resolve().parents[2]
H = ROOT / 'data/extended/power_c37'
OUT = ROOT / 'outputs/power_c37'
OUT.mkdir(parents=True, exist_ok=True)
EXP = ROOT / 'data/pi_adaptive_desktop/experiments'
L = 204800                                   # samples per frame (10.24 ms at 20 MS/s)
D1, D2 = 'C35/self_roll4_p70', 'C31/avg_whole_temporal'
POOL = ('silent', 'silent_cal')


def latest(stage):
    return EXP / 'campaigns' / json.loads((EXP / 'campaigns' / ('LATEST_' + stage + '.json')).read_text(encoding='utf-8-sig'))['campaign']


def cp(k, n):
    return [round(float(beta.ppf(.025, k, n - k + 1)), 3) if k else 0.0, round(float(beta.ppf(.975, k + 1, n - k)), 3) if k < n else 1.0]


def auc(pos, neg):
    pos, neg = np.array(pos, float), np.array(neg, float)
    if not len(pos) or not len(neg): return None
    return round(float(((pos[:, None] > neg[None, :]).sum() + .5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg))), 3)


def lin_db(v, w):
    return float(10 * np.log10(max(np.average(10 ** (np.asarray(v) / 10), weights=w), 1e-20)))


def em_window_stats(d, x):
    """p_pre: linear-mean wideband power over complete frames ending before the dispatch mark (as C35 subtracts);
    g: linear-mean wideband power over complete frames starting >= 2 frames after the reply mark, minus p_pre."""
    with np.load(d / 'features' / (x['id'] + '_930c.npz')) as f:
        w = f['sample_counts'].astype(float); power = f['power_db'].astype(float)
    end = np.cumsum(w); start = end - w
    before = next(m['bytes'] for m in x['before']['marks'] if m['radio'] == '930c') / 2
    after = next(m['bytes'] for m in x['after']['marks'] if m['radio'] == '930c') / 2
    full = w >= w.max()
    mp = (end <= before) & (w > 0); assert mp.sum() >= 4, x['id']
    mg = (start >= after + 2 * L) & full; assert mg.sum() >= 8, (x['id'], int(mg.sum()))
    p_pre = lin_db(power[mp], w[mp]); return p_pre, lin_db(power[mg], w[mg]) - p_pre


def load_em(d):
    rows = json.loads((d / 'RESULTS.json').read_text(encoding='utf-8'))
    preds = {}
    for fn in ('predictions_c35.csv', 'predictions_c31.csv'):
        for r in csv.DictReader(open(d / fn, encoding='utf-8')):
            if r['detector'] in (D1, D2):
                preds[(r['detector'], r['id'])] = (r['alert'] == 'True', float(r['score']))
    for x in rows:
        x['p_pre'], x['g'] = em_window_stats(d, x)
        for det, key in ((D1, 'D1'), (D2, 'D2')):
            a, s = preds[(det, x['id'])]; x[key + '_A'] = a; x[key + '_s'] = s
    return rows


# ---------------- power ----------------
def power_setup():
    tmf = H / 'c37_timemap.json'
    if not tmf.exists(): return None
    tm = json.loads(tmf.read_text(encoding='utf-8'))
    if not (H / tm['csv']).exists(): return None  # invalid power endpoint is excluded from this release
    snap = datetime.datetime.fromisoformat(tm['snapshot_utc'])
    a, b = tm['fit']['pi_utc_ms_rel_snapshot = a*csv_ms + b']
    ev = [json.loads((H / f).read_text(encoding='utf-8'))['events'] for f in sorted(H.glob('sync_pulses_c37p*.json'))]
    pairs = [tuple(int(v) for v in e[k].split()) for e in ev for k in ('clockpair', 'clockpair_end')]
    M0, R0 = pairs[0]; ms, mb = np.polyfit([p[0] - M0 for p in pairs], [p[1] - R0 for p in pairs], 1)
    r0_rel = (datetime.datetime(1970, 1, 1) + datetime.timedelta(microseconds=R0 / 1000) - snap).total_seconds() * 1000
    t, pw = np.loadtxt(H / tm['csv'], delimiter=',', skiprows=1, usecols=(10, 2), encoding='gbk').T[[0, 1]]

    def to_csv(ns):
        rel = r0_rel + (ms * (ns - M0) + mb) / 1e6
        return (rel - b) / a
    return {'t': t, 'pw': pw, 'to_csv': to_csv, 'fit': tm['fit']}


def power_feats(P, x):
    t, pw, f = P['t'], P['pw'], P['to_csv']
    s, e = f(x['private']['http_sent_ns']), f(x['private']['http_received_ns'])
    w = pw[np.searchsorted(t, s):np.searchsorted(t, e)]; pre = pw[np.searchsorted(t, s - 300):np.searchsorted(t, s)]
    return {'abs_win': float(w.mean()), 'peak500': float(np.convolve(w, np.ones(100) / 100, 'valid').max()), 'pre300': float(pre.mean())}


# ---------------- per-session derived detectors ----------------
def derive(rows, P):
    cal = [x for x in rows if x['condition'] == 'silent_cal']; assert len(cal) == 8
    g1_thr = max(x['p_pre'] for x in cal); g2_thr = max(x['g'] for x in cal)
    for x in rows:
        x['G1'] = x['p_pre'] > g1_thr; x['G1_m05'] = x['p_pre'] > g1_thr + .05; x['G1_m10'] = x['p_pre'] > g1_thr + .10
        x['G2'] = x['g'] > g2_thr; x['G2_m05'] = x['g'] > g2_thr + .05
    if P:
        for x in rows: x.update({'pw_' + k: v for k, v in power_feats(P, x).items()})
        calmean = np.mean([x['pw_peak500'] for x in cal]); hist = []
        for x in rows:                                     # rows are in collection order
            ref = calmean if (x['condition'] == 'silent_cal' or not hist) else float(np.mean(hist[-4:]))
            x['pw_peak500_roll4'] = x['pw_peak500'] - ref
            if x['condition'] in POOL: hist.append(x['pw_peak500'])
        for k in ('peak500_roll4', 'peak500', 'abs_win', 'pre300'):
            thr = max(x['pw_' + k] for x in cal)
            for x in rows: x['P_' + k] = x['pw_' + k] > thr
    return {'G1_threshold_dB': g1_thr, 'G2_threshold_dB': g2_thr}


def verdict(x, det):
    """Contract-conditioned alert: V = A_hat XOR E for D1/D2; guards and power are E = 0 call checks."""
    E = int(x.get('contract_E', 0))
    if det in ('D1', 'D2'): return x[det + '_A'] != bool(E)
    if det == 'D1+G1': return verdict(x, 'D1') or (x['G1'] and not E)
    if det == 'D2+G1': return verdict(x, 'D2') or (x['G1'] and not E)
    if det == 'P1+PG1': return x['P_peak500_roll4'] or x['P_pre300']
    if det.startswith('P_') or det.startswith('G'): return bool(x[det])
    raise KeyError(det)


def group(x, stage):
    if x['condition'] == 'silent_cal': return None
    if stage == 's1n': return x['condition'] + '/s1n'
    if x['condition'] == 'silent': return 'silent/' + ('clean' if not x.get('host_persist') else 'poisoned-probe')
    if x['condition'] in ('gzip16', 'gzip3_d19'): return x['condition'] + '/' + ('clean' if x.get('phase', 'clean') == 'clean' else 'poisoned-ref')
    return x['condition']


def main():
    P = power_setup(); out = {'utc': datetime.datetime.utcnow().isoformat() + 'Z', 'power': bool(P), 'sessions': {}}
    dets = ['D1', 'D2', 'G1', 'D1+G1', 'D2+G1', 'G2', 'G2_m05', 'G1_m05', 'G1_m10']
    if P: dets += ['P_peak500_roll4', 'P_peak500', 'P_abs_win', 'P_pre300', 'P1+PG1']; out['power_fit'] = P['fit']
    table = {}
    allrows = {}
    for stage in ('s1m', 's1n'):
        d = latest(stage); rows = load_em(d); thr = derive(rows, P); allrows[stage] = rows
        out['sessions'][stage] = {'campaign': d.name, 'n_rows': len(rows), **thr,
                                  'excluded_acquisition': len(json.loads((d / 'EXCLUDED.json').read_text(encoding='utf-8'))) if (d / 'EXCLUDED.json').exists() else 0}
        for x in rows:
            gk = group(x, stage)
            if gk is None: continue
            for det in dets:
                c = table.setdefault(gk, {}).setdefault(det, [0, 0]); c[0] += int(verdict(x, det)); c[1] += 1
    out['alerts'] = {g: {det: {'k': v[0], 'n': v[1], 'CI95': cp(*v)} for det, v in dd.items()} for g, dd in table.items()}
    # AUCs vs clean silents of the same session (s1m)
    rows = allrows['s1m']; neg = [x for x in rows if group(x, 's1m') == 'silent/clean']
    sc = {'D1': 'D1_s', 'D2': 'D2_s', 'G1(p_pre)': 'p_pre', 'G2(g)': 'g'}
    if P: sc.update({'P_peak500_roll4': 'pw_peak500_roll4', 'P_peak500': 'pw_peak500'})
    out['AUC_vs_clean_silent_s1m'] = {g: {k: auc([x[v] for x in rows if group(x, 's1m') == g], [x[v] for x in neg]) for k, v in sc.items()}
                                      for g in sorted({group(x, 's1m') for x in rows} - {None, 'silent/clean', 'silent_e1', 'gzip16_alt'})}
    # paired McNemar on s1m clean-phase attack cells: D1 vs D1+G1, D1 vs P1
    pairs = {}
    att = [x for x in rows if group(x, 's1m') in ('persist12', 'persist25', 'gzip16_p12')]
    for a_, b_ in (('D1', 'D1+G1'), ('D2', 'D1+G1'), ('D1', 'P_peak500_roll4'), ('D2', 'P_peak500_roll4')):
        if b_ not in dets: continue
        ao = sum(verdict(x, a_) and not verdict(x, b_) for x in att); bo = sum(verdict(x, b_) and not verdict(x, a_) for x in att)
        pairs[a_ + '_vs_' + b_] = {'a_only': ao, 'b_only': bo, 'p': binomtest(ao, ao + bo).pvalue if ao + bo else 1.0}
    out['mcnemar_masking_cells'] = pairs
    (OUT / 'c37_results.json').write_text(json.dumps(out, indent=1, default=float), encoding='utf-8')
    order = ['silent/clean', 'gzip16/clean', 'persist12', 'persist25', 'gzip16_p12', 'deferred16', 'silent_e1', 'gzip16_alt',
             'silent/poisoned-probe', 'gzip16/poisoned-ref', 'gzip3_d19/poisoned-ref', 'silent/s1n', 'gzip16/s1n', 'gzip3_d19/s1n']
    lines = ['| group | ' + ' | '.join(dets) + ' |', '|' + '---|' * (len(dets) + 1)]
    for g in order:
        if g in table: lines.append('| ' + g + ' | ' + ' | '.join('%d/%d' % tuple(table[g][det]) for det in dets) + ' |')
    (OUT / 'c37_results.md').write_text('# C37 results (alerts / runs; contract-conditioned for E=1 cells)\n\n' + '\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines)); print(json.dumps({k: out[k] for k in ('sessions', 'mcnemar_masking_cells')}, indent=1, default=float))


def dry(campaign):
    """Code check on an OLD campaign (e.g. C36 s1l): G1/G2 alert counts per condition; no C37 data touched."""
    d = pathlib.Path(campaign); rows = load_em(d); thr = derive(rows, None); by = {}
    for x in rows:
        b = by.setdefault(x['condition'], [0, 0, 0]); b[0] += int(x['G1']); b[1] += int(x['G2']); b[2] += 1
    print(json.dumps({'campaign': d.name, **thr, 'G1,G2,n by condition': by}, indent=1, default=float))


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--dry':
        dry(sys.argv[2])
    else:
        main()
