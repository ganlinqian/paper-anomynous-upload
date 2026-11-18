"""C36 (stage s1l) pre-specified analyses, fixed before any C36 run (2026-11-15 UTC; session ws_power).
Same endpoints as C35 (scripts/c35_stats.py), applied to the cross-day hold-out after a Pi reboot and probe re-mount:
  P1 primary detector (C35 self_roll4 p70) false alarms on the 40 test negatives (32 silent + 8 bg_log) <= 3/40;
  P2 primary detector hidden-work detections >= 44/48; C31 ensemble reported as the secondary detector.
Secondary (descriptive): primary false alarms and detections vs. the C35 batch (same layout, same boot as C34)
by two-sided Fisher exact test, to show whether reboot + re-mount changes either rate."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import c35_stats as S35


def main(campaign_dir=''):
    out = S35.main('s1l', 'c36_stats.json', campaign_dir)
    out['label'] = 'cross-day hold-out: Pi rebooted 2026-11-15, probes re-mounted, ~4 days after C35 (s1k)'
    p = S35.S.OUT / 'c36_stats.json'; p.write_text(json.dumps(out, indent=1), encoding='utf-8')
    print('label', out['label'])
    return out


if __name__ == '__main__':
    main(*(sys.argv[1:2]))
