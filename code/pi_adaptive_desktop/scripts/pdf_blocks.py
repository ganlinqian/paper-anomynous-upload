"""Print text blocks of selected pages (1-based) within a y range: x0 y0 x1 y1 text-prefix.

Usage: python -I pdf_blocks.py PAPER.pdf PAGES [YMIN YMAX [NCHARS]]   e.g. pdf_blocks.py main.pdf 12,13 0 200 80
"""
import sys
import fitz

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
doc = fitz.open(sys.argv[1])
pages = [int(p) for p in sys.argv[2].split(',')]
ymin = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
ymax = float(sys.argv[4]) if len(sys.argv) > 4 else 1e9
nch = int(sys.argv[5]) if len(sys.argv) > 5 else 80
for p in pages:
    for b in doc[p - 1].get_text('blocks'):
        if ymin <= b[1] <= ymax:
            print(f'p{p} {b[0]:4.0f} {b[1]:4.0f} {b[2]:4.0f} {b[3]:4.0f} {b[4][:nch]!r}')
