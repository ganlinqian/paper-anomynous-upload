"""Inspect a sample recording with the band layout of the paper's features (Section 6.3, Appendix B).

The samples are 8-bit interleaved I/Q at 20 MS/s (HackRF One, main receiver at 1.8 GHz), cropped so that the
recording starts 0.2 s before the coordinator's dispatch mark and ends 0.05 s after the reply mark (crops.json).
For each 10.24 ms frame, the script averages 200 Hann-windowed 1024-point power spectra, groups the bins with
0.15 MHz < |f| < 9 MHz into 64 bands of 10/64 MHz, and reports the band-average power of each quarter of the call
window relative to the pre-dispatch reference.

usage: python inspect_sample.py SAMPLE.iq.gz [SAMPLE2.iq.gz ...]
"""
import gzip, os, sys
import numpy as np

FS, FRAME, SUB, NFFT = 20_000_000, 204_800, 200, 1024
PRE_S, POST_S = 0.2, 0.05
f = np.fft.fftfreq(NFFT, 1 / FS)
band = np.minimum((64 * np.abs(f) / 10e6).astype(int), 63)
keep = (np.abs(f) > 0.15e6) & (np.abs(f) < 9e6)
win = np.hanning(NFFT).astype(np.float32)


def frame_bands(z):
    x = z.reshape(SUB, NFFT)
    x = x - x.mean(axis=1, keepdims=True)
    ps = (np.abs(np.fft.fft(x * win, axis=1)) ** 2).mean(axis=0)
    out = np.zeros(64)
    for b in np.unique(band[keep]):
        out[b] = ps[keep & (band == b)].mean()
    return out


for path in sys.argv[1:]:
    raw = np.frombuffer(gzip.open(path, "rb").read(), dtype=np.int8).astype(np.float32)
    z = raw[0::2] + 1j * raw[1::2]
    n = len(z) // FRAME
    B = np.array([frame_bands(z[i * FRAME:(i + 1) * FRAME]) for i in range(n)])
    used = B.mean(axis=0) > 0
    db = 10 * np.log10(B[:, used])
    t = np.arange(n) * FRAME / FS
    ref = db[t + FRAME / FS <= PRE_S].mean(axis=0)
    call = np.where((t >= PRE_S) & (t + FRAME / FS <= len(z) / FS - POST_S))[0]
    q = np.array_split(call, 4)
    rel = [float((db[idx] - ref).mean()) for idx in q]
    print(f"{os.path.basename(path)}: {len(call)} call-window frames; band-average power per quarter "
          f"(dB vs. pre-dispatch): " + "  ".join(f"Q{i+1} {v:+.2f}" for i, v in enumerate(rel)))
