import pathlib, json
from bridge_utils import *
from collect import preview_positive
B=pathlib.Path(__file__).resolve().parent
d=B/"positive_20261104_163253_188606"
lower_priority();w=connect("192.0.2.4","win");wf=w.open_sftp()
try:
    f=json.loads((d/"FREEZE.json").read_text())
    rows=[json.loads((d/"records"/cfg["id"]/"RECORD.json").read_text()) for cfg in f["plan"]]
    assert len(rows)==6 and all(r["valid"] for r in rows)
    assert sha(B/"collect_positive_original.py")==f["source_sha256"]["collect.py"]
    gate=preview_positive(wf,rows,d)
    save(d/"COMPLETE.json",{"stage":"positive","records":rows,"raw_bytes":sum(x["bytes"] for r in rows for x in r["rf"]["radios"]),"utc":stamp(),"freeze_sha256":sha(d/"FREEZE.json"),"report_recovery":"numpy bool to builtin bool only; RF unchanged; FAILURE.log retained","recovery_script_sha256":sha(__file__)})
    print(json.dumps({"pass":gate["pass"],"pairs":gate["pairs"],"primary_median_delta_db":gate["primary_median_delta_db"]}))
finally:wf.close();w.close()
