#!/usr/bin/env python3
"""Regenerate five figures from released statistics and features; no raw IQ or hardware needed."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code/pi_adaptive_desktop/scripts'))
import figstyle as style
import make_figures as core
import make_figures_v10 as desktop


def main():
    style.OUT = style.FIG_ROOT / 'selected'
    style.OUT.mkdir(parents=True, exist_ok=True)
    figures = {
        'fig_results': core.fig_results,
        'fig_budget': core.fig_budget,
        'fig_traces': core.fig_traces,
        'fig_contracts': desktop.fig_contracts,
        'fig_loadpower': desktop.fig_loadpower,
    }
    for name, build in figures.items():
        build()
        print('generated', name)
    report = {
        name: {key: value for key, value in core.REPORT[name].items() if key != 'preview'}
        for name in figures
    }
    target = style.OUT / 'figure_report.json'
    target.write_text(json.dumps(report, indent=2, default=str) + '\n')
    print('Figure outputs:', style.OUT.relative_to(ROOT))


if __name__ == '__main__':
    main()
