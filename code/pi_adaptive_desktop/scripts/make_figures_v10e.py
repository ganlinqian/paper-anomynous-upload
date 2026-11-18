"""v10 editorial pass: regenerate the figures whose colours were unified across the paper into figures/v10e.

Changes (all in make_figures_submission.py, data untouched): external timing is grey in the ROC panels (as in fig_results),
the C29 low-duty-plus-calibration model is navy in the frontier figure (navy = '+calibration' in fig_results), and the
teaser accuracy inset colours bars by method (white transcript, grey timing, sky whole-record, blue/navy system) with
hatching for the real-installer batch.  The build scripts copy figures/v10e last, so these files supply the submission plots.
usage: python -I make_figures_v10e.py [roc] [frontier] [inserts]
"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import figstyle as fs  # noqa: E402
import make_figures_submission as m8  # noqa: E402

fs.OUT = fs.FIG_ROOT / 'v10e'
todo = sys.argv[1:] or ['roc', 'frontier', 'inserts']
for name in todo:
    m8.BUILDERS[name]()
    print('regenerated', name, flush=True)
fs.OUT.mkdir(parents=True, exist_ok=True)
rep = {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != 'preview'}) for k, v in m8.REPORT.items()}
(fs.OUT / ('make_figures_v10e_report_' + '_'.join(todo) + '.json')).write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
for k, v in m8.REPORT.items():
    if isinstance(v, dict) and 'check' in v:
        print(k, json.dumps(v['check'], default=str)[:700])
