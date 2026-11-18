"""Anonymity/metadata check of a submission PDF (read-only).

Reports the Info dict, XMP packet, trailer /ID, PTEX.* keys left by pdfTeX on included graphics,
every CreationDate/ModDate string in any object (decompressed), and hits of identifying strings.
Usage: python -I pdf_meta_check.py PAPER.pdf [extra_pattern ...]
"""
import re, sys
import fitz

path = sys.argv[1]
doc = fitz.open(path)
print('pages:', doc.page_count)
print('info:', {k: v for k, v in doc.metadata.items() if v})
xmp = doc.get_xml_metadata()
print('xmp bytes:', len(xmp))
trailer = doc.pdf_trailer()
m = re.search(r'/ID\s*\[[^\]]*\]', trailer)
print('trailer /ID:', m.group(0)[:120] if m else None)
pats = ['user', 'Users', 'assistant', 'ws_main', 'zimeng', 'DESKTOP', "-08'00", 'Matplotlib', 'PTEX'] + sys.argv[2:]
ptex, names, dates, hits = 0, set(), set(), {p: 0 for p in pats}
for xref in range(1, doc.xref_length()):
    try:
        obj = doc.xref_object(xref, compressed=False)
    except Exception:
        continue
    if '/PTEX.' in obj:
        ptex += 1
        names.update(re.findall(r'/PTEX\.FileName\s*\(([^)]*)\)', obj))
    dates.update(re.findall(r'/(?:CreationDate|ModDate)\s*\(([^)]*)\)', obj))
    for p in pats:
        hits[p] += obj.count(p)
print('objects with PTEX keys:', ptex, '| PTEX.FileName:', sorted(names))
print('date strings in any object:', sorted(dates))
print('identifying-string hits in object dictionaries:', {k: v for k, v in hits.items() if v})
