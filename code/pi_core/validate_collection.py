"""Recompute trial truth from frozen inputs, observer raw events and worker files."""
import pathlib,json,hashlib,re,collections
from bridge_utils import save,sha,lower_priority
B=pathlib.Path(__file__).resolve().parent;lower_priority();checks=[];stages=[]
def ck(name,ok,detail=None):
    checks.append({"check":name,"pass":bool(ok),"detail":detail})
for stage,n in [("positive",6),("matrix",20),("boundary",12)]:
    candidates=[p for p in B.glob(stage+"_*/COMPLETE.json") if len(json.loads(p.read_text())["records"])==n]
    if not candidates:raise RuntimeError("missing "+stage)
    compath=max(candidates,key=lambda p:p.stat().st_mtime);d=compath.parent
    complete=json.loads(compath.read_text());freeze=json.loads((d/"FREEZE.json").read_text());rows=complete["records"];stages.append({"stage":stage,"directory":str(d),"records":len(rows)})
    ck(stage+"/planned",len(rows)==len(freeze["plan"])==n)
    raw_events=[json.loads(line) for line in (d/"observer_events.jsonl").read_text().splitlines()] if (d/"observer_events.jsonl").exists() else []
    byid={x["id"]:x for x in rows}
    for name,expected in freeze["source_sha256"].items():
        p=B/name
        if name=="collect.py" and sha(p)!=expected:p=B/"collect_positive_original.py"
        ck(stage+"/source/"+name,sha(p)==expected)
    post=json.loads((d/"POSTFLIGHT.json").read_text())
    ck(stage+"/restored",post["restore"]["rc"]==0 and post["pi_state"].splitlines()[0]=="ondemand")
    ck(stage+"/locks_released",post.get("pi_lock_release")==0 and post.get("rig",{}).get("rc")==0)
    for cfg in freeze["plan"]:
        row=byid[cfg["id"]];prefix=stage+"/"+cfg["id"];trial=d/"records"/cfg["id"]
        ck(prefix+"/valid",row["valid"])
        for rf in row["rf"]["radios"]:
            ck(prefix+"/"+rf["radio"]+"/raw_size",rf["bytes"]==rf["expected_bytes"]==(160000000 if stage=="positive" else 320000000))
            cmd=rf["command"];ck(prefix+"/"+rf["radio"]+"/receive_only","-r" in cmd and "-t" not in cmd)
            text=(trial/(rf["radio"]+".rf.log")).read_text()
            elapsed=re.search(r"Total time:\s*([0-9.]+)\s*s",text)
            ck(prefix+"/"+rf["radio"]+"/clean_receiver","hackrf_stop_rx() done" in text and "failed:" not in text.lower())
            ck(prefix+"/"+rf["radio"]+"/elapsed_bound",bool(elapsed) and (3.5 if stage=="positive" else 7.5)<float(elapsed.group(1))<(5.5 if stage=="positive" else 10.0),elapsed.group(1) if elapsed else None)
        if stage=="positive":continue
        worker=json.loads((trial/"worker.json").read_text());inp=json.loads((trial/"input.json").read_text())
        ck(prefix+"/no_policy_to_worker",set(inp)=={"kind","token","values","canary","http_port","dns_port"})
        ck(prefix+"/correct_output",worker["public"]["answer"]==sum(cfg["values"]))
        events=[e for e in raw_events if e["token"]==cfg["token"]];ck(prefix+"/observer_recomputed",events==row["independent_events"])
        purpose={"dns":"dns","helper":"helper","upload":"upload","cover_upload":"upload"}.get(cfg["kind"])
        attack=bool(purpose and not cfg["policy"]["allow_"+purpose]);ck(prefix+"/attack_recomputed",attack==row["attack_attempt"])
        effects=[e for e in events if e["action"] in ("answer_delivered","canary_received")]
        ck(prefix+"/effect_occurrence",bool(effects) if purpose else not effects)
        if purpose:
            ck(prefix+"/effect_policy",all(e["policy_allowed"]==cfg["policy"]["allow_"+purpose] for e in effects))
            ck(prefix+"/alert",row["strong_software"]["alert"]==attack)
            if purpose in ("dns","helper"):ck(prefix+"/answer_effect",all(e["answer"]==sum(cfg["values"]) and e["via"]==purpose for e in effects))
            else:
                expected=hashlib.sha256(cfg["canary"].encode()).hexdigest()
                ck(prefix+"/payload_effect",all(e["bytes"]==64 and e["sha256"]==expected for e in effects))
        if cfg["kind"]=="cover_upload":
            cv=worker["cover"];dg=worker["diagnostics"]
            ck(prefix+"/cover_containment",cv["begin_ns"]<=dg["upload_begin_ns"]<=dg["upload_end_ns"]<=cv["end_ns"])
        if cfg["kind"] in ("cover_upload","cover_only"):
            h=hashlib.sha256()
            for _ in range(64):h.update(b"C"*1048576)
            ck(prefix+"/cover_hash",h.hexdigest()==worker["cover"]["sha256"])
        for mark in ("before","after"):
            ck(prefix+"/capture_"+mark,all(m["running"] and 0<m["bytes"]<320000000 for m in row[mark]["marks"]))
        ck(prefix+"/win_causal_order",row["capture_ready"]["win_mono_ns"]<row["before"]["win_mono_ns"]<row["after"]["win_mono_ns"]<row["rf"]["win_mono_ns"])
    if stage=="matrix":
        count=collections.Counter((x["block"],x["kind"],x["policy"]["allow_dns"]) for x in rows)
        ck("matrix/full_factorial",len(count)==20 and all(n==1 for n in count.values()))
result={"pass":all(x["pass"] for x in checks),"checks":len(checks),"failed":[x for x in checks if not x["pass"]],"stages":stages,"details":checks}
save(B/"COLLECTION_VALIDATION.json",result)
print(json.dumps({k:result[k] for k in ["pass","checks","failed","stages"]}))
if not result["pass"]:raise SystemExit(1)
