import sys, fitz, re
doc = fitz.open(sys.argv[1])
keys = sys.argv[2:] if len(sys.argv) > 2 else ['References', 'REFERENCES', 'Appendix', 'APPENDIX', 'TABLE', 'Fig.', 'Conclusion', 'CONCLUSION']
print('pages', doc.page_count)
for i, page in enumerate(doc):
    t = page.get_text()
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    hits = sorted({k for k in keys if k in t})
    heads = [l for l in lines if re.match(r'^(\d+(\.\d+)?|[A-Z])\.?\s+[A-Z][A-Za-z ,:\-]{3,60}$', l)][:8]
    print(f'--- p{i+1} words={len(t.split())} hits={hits}')
    print('    first:', lines[0][:90] if lines else '')
    print('    heads:', heads)
    print('    last :', lines[-1][:90] if lines else '')
