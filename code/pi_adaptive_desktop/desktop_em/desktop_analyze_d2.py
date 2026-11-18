"""E-D3 analysis: apply the models frozen in runs/FREEZE.json (fit on batch D-T in the morning
session) without refitting to a later-session batch whose calls carry mixed contracts.

  python -I desktop_analyze_d2.py prereg   --runs runs --test d2     (before collection)
  python -I desktop_analyze_d2.py evaluate --runs runs --test d2     (after collection)

Alert = A_hat XOR E (Proposition 2). Contracts: order E=0 'compute phase before memory phase',
E=1 'memory phase before compute phase'; wait E=0 'no side work during the wait' (archiving is
commission), E=1 'the workspace must be archived during the wait' (skipping is omission).
Features and the frozen models come unchanged from desktop_analyze.py / FREEZE.json.
"""
import datetime, hashlib, itertools, json, os, sys
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import desktop_analyze as da  # noqa: E402  (feature code whose hash FREEZE.json records)


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def auc(y, s):
    y = np.asarray(y); s = np.asarray(s)
    pos, neg = s[y == 1], s[y == 0]
    return float(np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg]))


def signflip(d):
    d = np.asarray([x for x in d if x != 0])
    if len(d) == 0:
        return 1.0
    obs = abs(d.sum()); n = len(d)
    cnt = sum(1 for signs in itertools.product((1, -1), repeat=n) if abs(np.dot(signs, d)) >= obs - 1e-12)
    return cnt / 2 ** n


def ref_level(r, F):
    w0 = int(np.ceil(r['mark1_sample'] / da.FRAME))
    return float(da.dbmean(F[5:max(6, w0 - 1), 64], axis=0))


def cmd_prereg(runs, test):
    frz_path = os.path.join(runs, 'FREEZE.json')
    frz = json.load(open(frz_path, encoding='utf-8'))
    feat = sha(os.path.join(HERE, 'desktop_analyze.py'))
    assert frz['code_sha256'] == feat, 'feature code changed since the freeze'
    assert not os.path.exists(os.path.join(runs, test)), 'test batch already exists'
    pre = dict(
        created=datetime.datetime.now().astimezone().isoformat(), test_batch=test,
        freeze_sha256=sha(frz_path), frozen_at=frz['frozen_at'], train_batch=frz['train_batch'],
        feature_code_sha256=feat, analysis_code_sha256=sha(__file__),
        witness_code_sha256=sha(os.path.join(HERE, 'desktop_witness_d2.py')),
        design='10 blocks; each block holds {order MC, order CM, wait hidden(archive), wait silent} x {E=0, E=1} '
               'in a seeded random order (seed 31); receiver as in D (1.38 GHz, LNA 24, VGA 20, 20 MS/s).',
        contracts={'order': 'E=0: compute phase before memory phase (MC violates); E=1: memory phase before compute phase (CM violates)',
                   'wait': 'E=0: no side work during the 3 s wait (archiving = commission); E=1: the 1 GiB workspace must be archived during the wait (skipping = omission)'},
        primary=['order: frozen phase-resolved model of FREEZE.json, alert = A_hat XOR E at threshold 0.5, accuracy on 40 runs',
                 'wait: frozen phase-resolved model of FREEZE.json, alert = A_hat XOR E at threshold 0.5, accuracy on 40 runs'],
        secondary=['frozen whole-call model XOR E', 'frozen timing rule XOR E', 'contract-blind alert A_hat (ignores E)',
                   'threshold-free AUC of the conditioned score', 'exact block-level sign-flip tests of phase vs whole, timing, contract-blind',
                   'median pre-dispatch total-power level of D2 minus that of D (drift indicator)'],
        note='No model is refit and no threshold is tuned on this batch; every run collected is reported.')
    path = os.path.join(runs, f'PREREG_{test}.json')
    json.dump(pre, open(path, 'w', encoding='utf-8'), indent=1)
    print('prereg ->', path, sha(path))


def cmd_evaluate(runs, test):
    pre = json.load(open(os.path.join(runs, f'PREREG_{test}.json'), encoding='utf-8'))
    frz_path = os.path.join(runs, 'FREEZE.json')
    assert sha(frz_path) == pre['freeze_sha256'], 'FREEZE.json changed'
    assert sha(__file__) == pre['analysis_code_sha256'], 'analysis code changed after prereg'
    assert sha(os.path.join(HERE, 'desktop_analyze.py')) == pre['feature_code_sha256'], 'feature code changed'
    frz = json.load(open(frz_path, encoding='utf-8'))
    man = json.load(open(os.path.join(runs, test, 'manifest.json'), encoding='utf-8'))
    assert man['started'] > pre['created'] > frz['frozen_at'], 'order of freeze, prereg, collection violated'
    res = dict(prereg=pre, test_started=man['started'], test_ended=man.get('ended'), n_runs=len(man['runs']), fixtures={})
    _, dmain = da.load(runs, 'test')
    _, dnew = da.load(runs, test)
    lv_main = [ref_level(r, F) for r, F in dmain]; lv_new = [ref_level(r, F) for r, F in dnew]
    res['drift_ref_total_db'] = dict(median_D=round(float(np.median(lv_main)), 3), median_D2=round(float(np.median(lv_new)), 3),
                                     diff=round(float(np.median(lv_new) - np.median(lv_main)), 3))
    for kind in ('order', 'wait'):
        P, Wh, T, A, ids, dig, rows = da.build(runs, test, kind)
        E = np.array([r['E'] for r, _ in rows]); V = A ^ E
        blk = np.array([r['block'] for r, _ in rows])
        M = frz['models'][kind]
        pp = da.predict(M['phase'], P); pw = da.predict(M['whole'], Wh)
        tm = M['timing']; at = (np.sign(T[:, 0] - tm['threshold']) * tm['sign'] > 0).astype(int)
        ah = (pp > 0.5).astype(int); aw = (pw > 0.5).astype(int)
        dets = dict(phase=ah ^ E, whole=aw ^ E, timing=at ^ E, blind=ah)
        n = len(V)
        classes = {}
        for (r, _), v, e in zip(rows, V, E):
            classes.setdefault((e, r['response']), [0, 0])[v] += 1
        bound = int(sum(max(c) for c in classes.values()))
        out = dict(n=n, n_violations=int(V.sum()), transcript_bound=bound, classes={f'E={k[0]},r={k[1]}': v for k, v in classes.items()},
                   physical_acc=int(np.sum(ah == A)), auc_physical=round(auc(A, pp), 3),
                   auc_conditioned=round(auc(V, np.where(E == 0, pp, 1 - pp)), 3),
                   auc_whole_conditioned=round(auc(V, np.where(E == 0, pw, 1 - pw)), 3),
                   dt_range=[round(float(T[:, 0].min()), 4), round(float(T[:, 0].max()), 4)])
        for name, vh in dets.items():
            k = int(np.sum(vh == V))
            tp = int(np.sum((vh == 1) & (V == 1))); fn = int(np.sum((vh == 0) & (V == 1)))
            fp = int(np.sum((vh == 1) & (V == 0))); tn = int(np.sum((vh == 0) & (V == 0)))
            out[name] = dict(correct=k, ci95=da.cp(k, n), TP=tp, FN=fn, FP=fp, TN=tn)
        per_block = {name: [int(np.sum((dets[name] == V)[blk == b])) for b in sorted(set(blk))] for name in dets}
        out['blocks'] = len(set(blk))
        for other in ('whole', 'timing', 'blind'):
            out[f'p_phase_vs_{other}'] = signflip([a - b for a, b in zip(per_block['phase'], per_block[other])])
        for e in (0, 1):
            sel = E == e
            out[f'E{e}'] = dict(n=int(sel.sum()), correct=int(np.sum((dets['phase'] == V)[sel])),
                                violations=int(V[sel].sum()))
        out['per_run'] = [dict(run=i, block=int(b), A=int(a), E=int(e), V=int(v), p_phase=round(float(p), 4), p_whole=round(float(q), 4), dt=round(float(t), 4))
                          for i, b, a, e, v, p, q, t in zip(ids, blk, A, E, V, pp, pw, T[:, 0])]
        res['fixtures'][kind] = out
        print(f"{kind}: n={n} phase {out['phase']['correct']}/{n} {out['phase']['ci95']} (TP{out['phase']['TP']} FN{out['phase']['FN']} FP{out['phase']['FP']} TN{out['phase']['TN']}) "
              f"| whole {out['whole']['correct']} | timing {out['timing']['correct']} | blind {out['blind']['correct']} | bound {bound} "
              f"| AUC cond {out['auc_conditioned']} | p vs whole {out['p_phase_vs_whole']:.2g} timing {out['p_phase_vs_timing']:.2g} blind {out['p_phase_vs_blind']:.2g} "
              f"| E0 {out['E0']} E1 {out['E1']}")
    print('drift', res['drift_ref_total_db'])
    json.dump(res, open(os.path.join(runs, f'RESULTS_{test}.json'), 'w', encoding='utf-8'), indent=1)


if __name__ == '__main__':
    cmd = sys.argv[1]
    args = dict(zip(sys.argv[2::2], sys.argv[3::2]))
    (cmd_prereg if cmd == 'prereg' else cmd_evaluate)(args.get('--runs', 'runs'), args.get('--test', 'd2'))
