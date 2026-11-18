"""Whole-paper text audit of a built PDF: unresolved refs, key numbers, and where negative phrasing sits.

Usage: python -I text_audit.py PAPER.pdf
Prints, per page, hits of '??', key totals (819 captures, 424 GB, 41 hours / 39 hours), and evasion/negative
phrases, so that negative findings can be confirmed to sit in the evaluation data and the Discussion, not in
the abstract or introduction.
"""
import re, sys
import fitz

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
doc = fitz.open(sys.argv[1])
pages = [p.get_text() for p in doc]
heads = []
for i, t in enumerate(pages, 1):
    for m in re.finditer(r'^(\d{1,2})\. ([A-Z][A-Za-z ]{3,40})$', t, re.M):
        heads.append((i, m.start(), m.group(1) + '. ' + m.group(2)))


def section_of(page, pos):
    cur = 'Abstract/Title'
    for p, s, h in heads:
        if (p, s) <= (page, pos):
            cur = h
    return cur


checks = {
    'unresolved ??': r'\?\?',
    'captures total': r'\b(819|747|683) captures',
    'GB total': r'\b(424|378|337)\s?GB',
    'hours': r'\b(41|39|36) hours',
    'negative: evade/escape': r'\b(evad\w*|escap\w*)\b',
    'negative: sixteenth/eighth of a core': r'(sixteenth|eighth) of (a|one) core',
    'negative: not evaluated/untested': r'\b(untested|unevaluated|not evaluated)\b',
}
for name, pat in checks.items():
    hits = []
    for i, t in enumerate(pages, 1):
        flat = t.replace('-\n', '').replace('\n', ' ')
        for m in re.finditer(pat, flat):
            hits.append(f'p{i}[{section_of(i, t.find(m.group(0)[:6]))}]:{m.group(0)}')
    print(f'{name}: {len(hits)}')
    for h in hits[:14]:
        print('   ', h)
