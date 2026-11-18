"""IEEE compsoc figure style for the Telltale S&P paper (shared by make_figures.py).

Built on the scientific-visualization skill (K-Dense, v1.4, shared skills dir; byte-identical to upstream on
2026-11-06): its scoped style preset (style_presets.style_context: Okabe-Ito colours readable on white, Type 42
fonts, no top/right spines, white background) and its atomic exporter with a provenance manifest
(figure_export.export_figure).  Paper-specific additions: final sizes measured from IEEEtran compsoc conference
(\\columnwidth 243.91 pt = 3.375 in, \\textwidth 505.89 pt = 7.0 in; captions are 8 pt), so figures are included at
100 %; legend placement by measured ink under the legend; and an automated layout screen (clipping, text overlap,
legend over data, smallest font) with an ASCII preview.  The screen does not replace looking at the figure.
"""
import contextlib, hashlib, itertools, os, pathlib, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib as mpl
from matplotlib.collections import LineCollection
from matplotlib.path import Path as MPath
from matplotlib.text import Text

# Project paths. Each can be redirected by an environment variable so that a copy of the scripts and data (e.g. the
# source package) regenerates the figures elsewhere; the defaults are the project paths.
REPOSITORY = pathlib.Path(__file__).resolve().parents[3]
ROOT = pathlib.Path(os.environ.get('TELLTALE_SP2027', str(REPOSITORY / 'data/pi_adaptive_desktop')))
FIG_ROOT = pathlib.Path(os.environ.get('TELLTALE_FIGURES', str(REPOSITORY / 'outputs/figures')))
SKILL = pathlib.Path(os.environ.get('TELLTALE_SCIVIS', str(REPOSITORY / 'code/third_party/scientific-visualization')))
sys.path.insert(0, str(SKILL / 'scripts'))
from style_presets import style_context  # noqa: E402  (skill code, reviewed 2026-11-06)
from figure_export import export_figure  # noqa: E402

OUT = FIG_ROOT / 'v7'
COL_W = 243.91125 / 72.27          # 3.375 in
FULL_W = 505.89 / 72.27            # 7.0 in
SYS = 'Telltale'                   # system name shown in figure labels (v9)
# Okabe-Ito (Wong 2011) colours from the skill's references/color_palettes.md; NAVY is a darker step of BLUE.
BLUE, VERM, GREEN, PURPLE, SKY = '#0072B2', '#D55E00', '#009E73', '#CC79A7', '#56B4E9'
NAVY, GREY, EDGE = '#00324F', '#C8C8C8', '#333333'

IEEE_RC = {
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'DejaVu Sans'],
    'mathtext.fontset': 'custom', 'mathtext.rm': 'Arial', 'mathtext.it': 'Arial:italic', 'mathtext.bf': 'Arial:bold',
    'font.size': 8, 'axes.labelsize': 8, 'axes.titlesize': 8, 'xtick.labelsize': 7, 'ytick.labelsize': 7,
    'legend.fontsize': 7, 'axes.titlelocation': 'left', 'axes.titlepad': 3, 'axes.labelpad': 2,
    'xtick.major.pad': 2, 'ytick.major.pad': 2, 'lines.linewidth': 1.0, 'lines.markersize': 3.5,
    'patch.linewidth': 0.5, 'hatch.linewidth': 0.5, 'legend.handlelength': 1.8, 'legend.handletextpad': 0.4,
    'legend.columnspacing': 1.0, 'legend.borderaxespad': 0.3, 'legend.borderpad': 0.2,
    'figure.constrained_layout.h_pad': 0.02, 'figure.constrained_layout.w_pad': 0.02,
}


@contextlib.contextmanager
def ieee_style(**over):
    with style_context('default', palette_name='okabe_ito_on_white'):
        with mpl.rc_context({**IEEE_RC, **over}):
            yield


def skill_fingerprint():
    files = ['LICENSE.md', 'scripts/style_presets.py', 'scripts/figure_export.py', 'assets/color_palettes.py']
    return {'package': 'scientific-visualization', 'version': '1.4',
            'sha256': {f: hashlib.sha256((SKILL / f).read_bytes()).hexdigest()[:16] for f in files}}


def save(fig, name, provenance):
    """PDF for the paper (Type 42 fonts, no dates or producer) + 300 dpi PNG preview + export manifest."""
    return export_figure(fig, OUT / name, formats=('pdf', 'png'), dpi=300, bbox_inches=None, overwrite=True,
                         mkdir=True, metadata={'Creator': 'matplotlib', 'Producer': None, 'CreationDate': None},
                         provenance={**provenance, 'style': skill_fingerprint()}, write_manifest=True)


def _drawn_texts(fig, r):
    """(Text, bbox) of every non-empty text that is actually drawn (tick labels outside the view are skipped)."""
    tick_ids, drawn = set(), []
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                tick_ids.update({id(tick.label1), id(tick.label2)})
            for tick in axis._update_ticks():
                drawn += [lab for lab in (tick.label1, tick.label2) if lab.get_visible() and lab.get_text().strip()]
    drawn += [t for t in fig.findobj(Text) if id(t) not in tick_ids and t.get_visible() and t.get_text().strip()]
    out = []
    for t in drawn:
        bb = t.get_window_extent(r)
        if bb.width > 0 and bb.height > 0:
            out.append((t, bb))
    return out


def _legend_hits(ax, r):
    leg = ax.get_legend()
    if leg is None:
        return None
    lb = leg.get_window_extent(r)
    hits = []
    for ln in ax.get_lines():
        xy = ln.get_transform().transform(np.asarray(ln.get_xydata(), float))
        if len(xy) > 1 and MPath(xy).intersects_bbox(lb, filled=False):
            hits.append('line:' + str(ln.get_label()))
    for coll in ax.collections:
        for p in coll.get_paths():
            if p.transformed(coll.get_transform()).intersects_bbox(lb, filled=True):
                hits.append('area:' + str(coll.get_label()))
                break
    hits += ['patch' for p in ax.patches if p.get_window_extent(r).overlaps(lb)]
    return hits


def check_layout(fig, min_font=6.5):
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    W, H = fig.bbox.width, fig.bbox.height
    texts = _drawn_texts(fig, r)
    issues = []
    for t, bb in texts:
        if bb.x0 < -0.5 or bb.y0 < -0.5 or bb.x1 > W + 0.5 or bb.y1 > H + 0.5:
            issues.append(f'clipped: {t.get_text()!r}')
        if t.get_fontsize() < min_font:
            issues.append(f'small font {t.get_fontsize():.1f}pt: {t.get_text()!r}')
    for (t1, b1), (t2, b2) in itertools.combinations(texts, 2):
        if min(b1.x1, b2.x1) - max(b1.x0, b2.x0) > 0.5 and min(b1.y1, b2.y1) - max(b1.y0, b2.y0) > 0.5:
            issues.append(f'text overlap: {t1.get_text()!r} / {t2.get_text()!r}')
    legend_hits = {}
    for i, ax in enumerate(fig.axes):
        h = _legend_hits(ax, r)
        if h:
            legend_hits[ax.get_title(loc='left') or f'axes{i}'] = h
        # annotations placed on the data (e.g. counts in bars) must not sit on error bars or data lines
        for t in ax.texts:
            if not (t.get_visible() and t.get_text().strip()):
                continue
            tb = t.get_window_extent(r)
            for coll in ax.collections:
                if isinstance(coll, LineCollection) and any(
                        MPath(coll.get_transform().transform(np.asarray(s, float))).intersects_bbox(tb, filled=False)
                        for s in coll.get_segments() if len(s) > 1):
                    issues.append(f'text on data line: {t.get_text()!r}')
            for ln in ax.get_lines():
                xy = ln.get_transform().transform(np.asarray(ln.get_xydata(), float))
                if ln.get_linestyle() in ('None', 'none', '', ' '):
                    hit = bool(((xy[:, 0] > tb.x0) & (xy[:, 0] < tb.x1) & (xy[:, 1] > tb.y0) & (xy[:, 1] < tb.y1)).any())
                else:
                    hit = len(xy) > 1 and MPath(xy).intersects_bbox(tb, filled=False) and ln.get_zorder() >= t.get_zorder() - 2
                if hit:
                    issues.append(f'text on line/marker {ln.get_label()!r}: {t.get_text()!r}')
    sizes = sorted({round(t.get_fontsize(), 2) for t, _ in texts})
    return {'figure_in': [round(v, 3) for v in fig.get_size_inches()], 'n_texts': len(texts),
            'font_sizes_pt': sizes, 'issues': issues, 'legend_over_data': legend_hits}


def best_legend_loc(fig, ax, candidates, **kw):
    """Place the legend at the candidate location with the least plotted ink underneath it (rendered check)."""
    boxes = []
    for loc in candidates:
        leg = ax.legend(loc=loc, **kw)
        fig.canvas.draw()
        boxes.append(leg.get_window_extent(fig.canvas.get_renderer()))
        leg.remove()
    fig.canvas.draw()
    img = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].min(axis=2)
    h = img.shape[0]
    ink = []
    for bb in boxes:
        y0, y1 = int(h - bb.y1), int(h - bb.y0)
        sub = img[max(0, y0):max(0, y1), max(0, int(bb.x0)):max(0, int(bb.x1))]
        ink.append(float((sub < 235).mean()) if sub.size else 1.0)
    j = int(np.argmin(ink))
    ax.legend(loc=candidates[j], **kw)
    return candidates[j], round(ink[j], 4), {c: round(v, 4) for c, v in zip(candidates, ink)}


def ascii_preview(png_path, cols=150, rows=None):
    from PIL import Image
    im = Image.open(png_path).convert('L')
    w, h = im.size
    rows = rows or max(4, int(round(h / w * cols * 0.5)))
    a = np.asarray(im.resize((cols, rows), Image.BOX), float) / 255.0
    ramp = ' .:-=+*#%@'
    return '\n'.join(''.join(ramp[min(9, int((1.0 - v) * 10))] for v in row) for row in a)
