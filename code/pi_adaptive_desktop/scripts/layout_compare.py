"""Where do section heads, figure/table captions and References fall (page, y in pt from top)?  Compares PDFs.

Usage: python -I layout_compare.py A.pdf [B.pdf]   (prints both side by side when B is given)
"""
import re, sys
import fitz

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PAT = re.compile(r'^(Figure \d+\.|TABLE \d+\.|TABLE [IVX]+|\d{1,2}\. [A-Z][A-Za-z ,:\-]{2,40}$|References$|REFERENCES$|Appendix [A-Z]|APPENDIX [A-Z])')


def marks(path):
    doc = fitz.open(path)
    out = {}
    for pno, page in enumerate(doc, 1):
        for b in page.get_text('blocks'):
            first = b[4].strip().split('\n')[0].strip()
            m = PAT.match(first)
            if m:
                key = m.group(1) if first.startswith(('Figure', 'TABLE')) else first[:40]
                out.setdefault(key, (pno, round(b[1], 1)))
    return doc.page_count, out


na, a = marks(sys.argv[1])
if len(sys.argv) > 2:
    nb, b = marks(sys.argv[2])
    print(f'pages: {na} -> {nb}')
    for k in sorted(set(a) | set(b), key=lambda k: (a.get(k, b.get(k))[0], a.get(k, b.get(k))[1])):
        print(f'{k:42s} {str(a.get(k)):>14s} -> {str(b.get(k)):>14s}' + ('' if a.get(k) == b.get(k) else '   *'))
else:
    print('pages', na)
    for k, v in sorted(a.items(), key=lambda kv: kv[1]):
        print(f'{k:42s} {v}')
