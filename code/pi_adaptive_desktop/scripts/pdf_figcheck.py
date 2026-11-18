"""Text-overlap screen for a compiled figure page (vector text from TikZ and embedded plots).

Usage: python -I pdf_figcheck.py FILE.pdf [PAGE(1-based)]
Reports the bounding box of all drawings and words, and pairs of words whose boxes overlap by more than
25% of the smaller box (different lines), which usually means colliding labels.  Not a substitute for viewing.
"""
import itertools, sys
import fitz

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
doc = fitz.open(sys.argv[1])
pno = int(sys.argv[2]) - 1 if len(sys.argv) > 2 else 0
page = doc[pno]
words = page.get_text('words')
# hatch fills are tiling patterns whose cells can extend past the page; ignore drawings outside the page
draw = [d for d in page.get_drawings() if page.rect.contains(d['rect'])]
xs = [w[0] for w in words] + [d['rect'].x0 for d in draw]
ys = [w[1] for w in words] + [d['rect'].y0 for d in draw]
xe = [w[2] for w in words] + [d['rect'].x1 for d in draw]
ye = [w[3] for w in words] + [d['rect'].y1 for d in draw]
ACCENTS = set('ˆ˜¯˙´`ˇ˘')
print(f'page {pno + 1}: {len(words)} words, {len(draw)} drawings; content bbox x {min(xs):.1f}-{max(xe):.1f} '
      f'({(max(xe) - min(xs)) / 72:.2f} in), y {min(ys):.1f}-{max(ye):.1f} ({(max(ye) - min(ys)) / 72:.2f} in)')
issues = 0
for a, b in itertools.combinations(words, 2):
    if (a[5], a[6]) == (b[5], b[6]) or a[4] in ACCENTS or b[4] in ACCENTS:
        continue
    ix = min(a[2], b[2]) - max(a[0], b[0]); iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix <= 0 or iy <= 0:
        continue
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    if small > 0 and ix * iy / small > 0.25:
        issues += 1
        print(f'  overlap: {a[4]!r} @({a[0]:.0f},{a[1]:.0f}) / {b[4]!r} @({b[0]:.0f},{b[1]:.0f})  {ix * iy / small:.0%}')
print('overlapping word pairs:', issues)
