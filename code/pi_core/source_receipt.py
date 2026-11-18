"""Source-side streaming integrity hashes only, no numerical IQ processing."""
import ctypes,hashlib,json,pathlib,sys,time
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
src=pathlib.Path(sys.argv[1]);files=json.loads(src.read_text())["files"];rows=[]
for row in files:
    p=pathlib.Path(row["source_raw"]);h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
    if p.stat().st_size!=row["expected_bytes"]:raise RuntimeError("source size mismatch")
    rows.append({"filename":row["filename"],"source_raw":str(p),"bytes":p.stat().st_size,"sha256":h.hexdigest()})
out=src.with_name("SOURCE_RECEIPTS.json");out.write_text(json.dumps({"files":rows,"scope":"source-side integrity read only"},indent=2))
print(json.dumps({"files":len(rows),"bytes":sum(x["bytes"] for x in rows),"receipt":str(out)}))
