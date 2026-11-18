"""capture_pc-local contiguous IQ feature extraction (no models).

The per-file computation is a verbatim copy of `one()` in remote_extract_confirmation.py
(session ws_pi, SHA c387e3c7...), only the I/O wrapper differs: files are read in place
on the capture PC and only the small feature files leave it.  Runs at BELOW_NORMAL priority.
Usage: python win4_extract.py --list files.json --out OUTDIR [--workers 2]
files.json: [{"path": "<DRIVE>/.../x_930c.iq", "id": "...", "radio": "930c", "expected_bytes": 320000000}, ...]
"""
import argparse, concurrent.futures, ctypes, hashlib, json, os, pathlib, time, traceback
os.environ["OPENBLAS_NUM_THREADS"] = "1"; os.environ["OMP_NUM_THREADS"] = "1"; os.environ["MKL_NUM_THREADS"] = "1"
import numpy as np
NFFT = 1024; SEG = 204800; SR = 20000000

def below_normal():
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    except Exception:
        pass

def save(p, x):
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(x, ensure_ascii=False, indent=2)); tmp.replace(p)

def one(task):
    below_normal()
    raw = pathlib.Path(task["path"]); out = pathlib.Path(task["out"]) / (raw.stem + ".npz")
    h = hashlib.sha256(); band = np.minimum((np.abs(np.fft.fftfreq(NFFT, 1 / SR)) / 1e7 * 64).astype(int), 63)
    valid = (np.abs(np.fft.fftfreq(NFFT, 1 / SR)) > .15e6) & (np.abs(np.fft.fftfreq(NFFT, 1 / SR)) < 9e6)
    groups = [np.where(valid & (band == j))[0] for j in range(64)]; empty = [j for j, g in enumerate(groups) if not len(g)]
    win = np.hanning(NFFT).astype(np.float32); den = float(np.sum(win ** 2) * NFFT)
    series = []; powers = []; clips = []; counts = []; consumed = 0
    with raw.open("rb") as f:
        while True:
            buf = f.read(SEG * 2)
            if not buf:
                break
            h.update(buf); a = np.frombuffer(buf, dtype=np.int8); consumed += len(a)
            if len(a) % 2:
                raise RuntimeError("odd IQ byte count")
            z = a[0::2].astype(np.float32) + 1j * a[1::2].astype(np.float32)
            if len(z) % NFFT:
                raise RuntimeError("tail not FFT aligned")
            powers.append(float(np.mean(z.real * z.real + z.imag * z.imag))); counts.append(len(z))
            clips.append(float(np.mean((a == -128) | (a == 127))))
            frames = z.reshape(-1, NFFT); frames = frames - frames.mean(axis=1, keepdims=True)
            fft = np.fft.fft(frames * win, axis=1); sp = np.mean(fft.real ** 2 + fft.imag ** 2, axis=0) / den
            series.append(np.array([float(np.mean(sp[g])) if len(g) else 0 for g in groups]))
    if consumed != raw.stat().st_size or consumed != task["expected_bytes"]:
        raise RuntimeError("incomplete extraction")
    psd = np.array(series); pw = np.array(powers); ct = np.array(counts); db = 10 * np.log10(np.maximum(psd, 1e-20)); pwdb = 10 * np.log10(np.maximum(pw, 1e-20))
    mean_db = 10 * np.log10(np.maximum(np.average(psd, axis=0, weights=ct), 1e-20))
    feat = np.concatenate([mean_db, np.quantile(db, [.1, .5, .9], axis=0).ravel(), [10 * np.log10(np.average(pw, weights=ct))], np.quantile(pwdb, [.1, .5, .9])])
    for j in empty:
        for k in range(4):
            feat[j + k * 64] = 0
    np.savez_compressed(out, features=feat, power_db=pwdb, band_db=db, clip_fraction=np.array(clips), sample_counts=ct)
    result = {"id": task["id"], "radio": task["radio"], "filename": raw.name, "raw_sha256": h.hexdigest(), "raw_bytes": consumed,
              "feature_path": str(out), "frames": len(pw), "samples_consumed": int(ct.sum()), "full_contiguous": True,
              "empty_frequency_groups": empty, "feature_dim": len(feat), "mean_power_db": float(10 * np.log10(np.average(pw, weights=ct))),
              "max_clip_fraction": float(max(clips)), "extractor": "win4_extract.py", "numpy": np.__version__}
    save(out.with_suffix(".json"), result); return result

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--list", required=True); ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args(); below_normal()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tasks = json.loads(pathlib.Path(a.list).read_text(encoding="utf-8-sig"))
    todo = [dict(t, out=str(out)) for t in tasks if not (out / (pathlib.Path(t["path"]).stem + ".json")).exists()]
    start = time.time(); done = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(one, todo):
            done.append(r); print(json.dumps({"completed": len(done), "of": len(todo), "file": r["filename"], "s": round(time.time() - start, 1)}), flush=True)
            save(out / "EXTRACTION_STATUS.json", {"completed": len(done), "todo": len(todo), "elapsed_s": time.time() - start})
    save(out / "EXTRACTION_COMPLETE.json", {"files": len(tasks), "newly_extracted": len(done), "elapsed_s": time.time() - start})

if __name__ == "__main__":
    try:
        main()
    except Exception:
        pathlib.Path(__file__).with_name("WIN4_EXTRACTION_FAILURE.log").write_text(traceback.format_exc()); raise
