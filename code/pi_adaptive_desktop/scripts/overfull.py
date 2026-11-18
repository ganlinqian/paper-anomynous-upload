import re, sys, pathlib
log = pathlib.Path(sys.argv[1]).read_text(encoding='latin-1')
stack = []
out = []
i = 0
tok = re.compile(r'\((\./)?([A-Za-z0-9_\-/]+\.(tex|bbl))|\)|Overfull \\hbox \(([\d.]+)pt too wide\) in (paragraph|alignment) at lines (\d+)--(\d+)')
for m in tok.finditer(log):
    if m.group(2):
        stack.append(m.group(2))
    elif m.group(0) == ')':
        if stack:
            stack.pop()
    elif m.group(4):
        out.append((stack[-1] if stack else '?', float(m.group(4)), m.group(6), m.group(7)))
for f, w, a, b in out:
    print(f'{f:28s} {w:7.2f}pt lines {a}-{b}')
