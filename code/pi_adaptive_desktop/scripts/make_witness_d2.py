"""Derive desktop_witness_d2.py (E-D3) from desktop_witness.py without touching the original.

The only change is a --contracts option: 'mixed' runs every variant once under contract bit E=0
and once under E=1 and records E per run; capture, binding, and features are unchanged.
"""
import hashlib, os, sys

D = r'<WORKSPACE>/ws_main\results\sp2027\desktop_em'
src = open(os.path.join(D, 'desktop_witness.py'), encoding='utf-8').read()
reps = [
    ("usage: python -I desktop_witness.py --batch train --blocks 12 --seed 1\n",
     "usage: python -I desktop_witness.py --batch train --blocks 12 --seed 1\n\n"
     "E-D3 copy (desktop_witness_d2.py): adds --contracts mixed, which runs every variant once under\n"
     "contract bit E=0 and once under E=1 and records E per run. Contracts: order E=0 'compute phase\n"
     "before memory phase', E=1 'memory phase before compute phase'; wait E=0 'no side work during\n"
     "the wait', E=1 'the workspace must be archived during the wait'. The host never sees E.\n"),
    ("    ap.add_argument('--kinds', default='order,wait')\n",
     "    ap.add_argument('--kinds', default='order,wait')\n"
     "    ap.add_argument('--contracts', default='fixed', help='fixed: E=0 for every call; mixed: each variant under E=0 and E=1')\n"),
    ("    variants = [v for v in [('order', 'MC'), ('order', 'CM'), ('wait', 'hidden'), ('wait', 'silent')] if v[0] in kinds]\n",
     "    base = [v for v in [('order', 'MC'), ('order', 'CM'), ('wait', 'hidden'), ('wait', 'silent')] if v[0] in kinds]\n"
     "    variants = [(k, v, e) for k, v in base for e in ((0, 1) if a.contracts == 'mixed' else (0,))]\n"),
    ("hidden=a.hidden,\n                    host=socket.gethostname()",
     "hidden=a.hidden, contracts=a.contracts,\n                    host=socket.gethostname()"),
    ("        for i, (blk, kind, variant) in enumerate(schedule):\n",
     "        for i, (blk, kind, variant, E) in enumerate(schedule):\n"),
    ("A=int(variant in ('MC', 'hidden')),\n",
     "A=int(variant in ('MC', 'hidden')), E=int(E),\n"),
    ("print(f\"{rid} blk={blk} {kind}/{variant} dt=",
     "print(f\"{rid} blk={blk} {kind}/{variant} E={E} dt="),
]
for old, new in reps:
    n = src.count(old)
    if n != 1:
        sys.exit(f'pattern count {n} != 1: {old[:60]!r}')
    src = src.replace(old, new)
out = os.path.join(D, 'desktop_witness_d2.py')
open(out, 'w', encoding='utf-8', newline='\n').write(src)
print(out, hashlib.sha256(src.encode('utf-8')).hexdigest())
