"""Per-run quarter means (band-average and total power, dB re. pre-dispatch window)."""
import json, os, sys
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
root, batch = sys.argv[1], sys.argv[2]
m = json.load(open(os.path.join(root, batch, 'manifest.json'), encoding='utf-8'))
for r in m['runs']:
    F = np.load(os.path.join(root, batch, r['run'] + '.npy'))
    w0 = r['mark1_sample'] // 204800 + 1; w1 = r['mark2_sample'] // 204800
    good = ~np.all(np.isnan(F[:, :64]), 0)
    B = 10 * np.log10(np.nanmean(10 ** (F[:, :64][:, good] / 10), 1)); T = F[:, 64]
    ref, refT = B[5:w0 - 1].mean(), T[5:w0 - 1].mean()
    seg = np.array_split(B[w0:w1] - ref, 4); segT = np.array_split(T[w0:w1] - refT, 4)
    print(f"{r['run']} {r['kind']:5s} {r['variant']:6s} band q: " + ' '.join(f'{s.mean():+.2f}' for s in seg) + '  total q: ' + ' '.join(f'{s.mean():+.2f}' for s in segT))
