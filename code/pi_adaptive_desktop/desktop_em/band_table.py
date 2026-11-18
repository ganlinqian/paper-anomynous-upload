"""Per-sweep sub-band power (dB) at chosen 20-MHz bands, to check repeatability."""
import sys, os, json
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
d = sys.argv[1]
bands = [int(x) for x in sys.argv[2].split(',')]
meta = json.load(open(os.path.join(d, 'meta.json'), encoding='utf-8'))
los = (np.array(meta['los_hz']) / 1e6).astype(int)
NF = 1024
keep = np.ones(NF, bool); keep[NF//2-8:NF//2+8] = False; keep[:64] = False; keep[-64:] = False
for b in bands:
    bi = int(np.where(los == b)[0][0])
    print(f'== band centred {b} MHz: rows=sweep, cols=8 sub-bands of 2.5 MHz (dB)')
    for s in meta['sweeps']:
        P = np.load(os.path.join(d, f"sweep_{s['k']:02d}_{s['cond']}.npy"))[bi]
        vals = []
        for j in range(8):
            sl = slice(j * 128, (j + 1) * 128)
            m = keep[sl]
            vals.append(10 * np.log10(np.mean(10 ** (P[sl][m] / 10))) if m.sum() else np.nan)
        print(f"  {s['k']} {s['cond']} " + ' '.join(f'{v:7.2f}' for v in vals))
