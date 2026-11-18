"""Print selected core-study results (C08--C29 and x86 desktop) from saved statistics in data/.

usage: python check_numbers.py
Each line names the batch, the branch, correct/total (or alerts/runs), and the source file.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
STATS = os.path.join(HERE, "data", "pi_adaptive_desktop", "stats")
DESK = os.path.join(HERE, "data", "pi_adaptive_desktop", "desktop_em", "runs")


def load(*p):
    with open(os.path.join(*p), encoding="utf-8") as f:
        return json.load(f)


def branches(d, prefix=""):
    """Yield (path, dict) for every dict that carries correct/n counts."""
    if isinstance(d, dict):
        if "correct" in d and "n" in d:
            yield prefix, d
        for k, v in d.items():
            yield from branches(v, f"{prefix}/{k}" if prefix else str(k))


paper = load(STATS, "paper_stats.json")
print("== Raspberry Pi, C08--C15 (stats/paper_stats.json)")
for batch in paper:
    for path, b in branches(paper[batch]):
        auc = f", AUC {b['auc']:.2f}" if isinstance(b.get("auc"), (int, float)) else ""
        print(f"  {batch:22} {path:46} {b['correct']}/{b['n']}{auc}")

supp = load(STATS, "supp_stats.json")
print("== Raspberry Pi, C24--C28 (stats/supp_stats.json): primary model, alerts/runs per condition")
names = {"s1": "C24", "s3": "C25", "s1b": "C27", "s1c": "C28"}
for key, label in names.items():
    s = supp.get(key, {})
    cond = s.get("primary_by_condition", {})
    if cond:
        print(f"  {label}: " + ", ".join(f"{c} {v['alerts']}/{v['n']}" for c, v in cond.items()))
s2 = supp.get("s2", {})
for name, m in s2.get("models", {}).items():
    if isinstance(m, dict) and "correct" in m:
        print(f"  C26 {name:20} {m['correct']}/{m.get('n', s2.get('n'))}")

c29 = load(STATS, "c29_stats.json")
print("== C29 (stats/c29_stats.json): primary " + c29.get("primary", "?"))
print("  " + ", ".join(f"{c} {v['alerts']}/{v['n']}" for c, v in c29["primary_by_condition"].items())
      + f", silent {c29['primary_silent_false_alarms']['alerts']}/{c29['primary_silent_false_alarms']['n']}")

print("== x86 desktop (desktop_em/runs)")
t = load(DESK, "STATS_test.json")
for fam in ("order", "wait"):
    s = t[fam]
    print(f"  D {fam:6} TP {s['TP']} FN {s['FN']} FP {s['FP']} TN {s['TN']} (correct {s['TP'] + s['TN']}/{s['n']})")
d2 = load(DESK, "RESULTS_d2.json")
for fam, s in d2["fixtures"].items():
    print(f"  D2 {fam:6} physical-bit correct {s.get('physical_acc')}/{s['n']}, transcript bound {s['transcript_bound']}/{s['n']}")
print(f"  idle-level drift between D and D2: {d2['drift_ref_total_db']['diff']} dB")
