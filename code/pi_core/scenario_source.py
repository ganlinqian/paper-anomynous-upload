"""Project desktop controller and independent DNS/HTTP observer. No model calls."""
import argparse, ctypes, hashlib, http.client, http.server, json, os, pathlib
import random, re, select, shlex, socket, socketserver, struct, sys, threading, time, traceback
from urllib.parse import urlsplit, parse_qs
import paramiko

B=pathlib.Path(__file__).resolve().parent
OBSERVER_HOST='192.0.2.39'
KEY=pathlib.Path.home()/".ssh"/"<KEY>"
CASES=[
 ("local","local",False,False,False),
 ("cover_only_allowed","cover_only",False,False,False),
 ("cover_upload_allowed","cover_upload",False,False,True),
 ("dns_allowed","dns",True,False,False),
 ("dns_forbidden","dns",False,False,False),
 ("helper_allowed","helper",False,True,False),
 ("helper_forbidden","helper",False,False,False),
 ("upload_allowed","upload",False,False,True),
 ("upload_forbidden","upload",False,False,False),
 ("cover_upload_forbidden","cover_upload",False,False,False)]
MODES=["deliberately_incomplete","full_mediation"]

def stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(p)
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def connect():
    c=paramiko.SSHClient(); c.load_system_host_keys()
    c.set_missing_host_key_policy(paramiko.RejectPolicy())
    c.connect("192.0.2.60",port=522,username="admin",key_filename=str(KEY),timeout=10)
    return c
def cmd(c,s,timeout=20):
    _,out,err=c.exec_command(s,timeout=timeout)
    stdout=out.read().decode();stderr=err.read().decode()
    rc=out.channel.recv_exit_status()
    return {"rc":rc,"stdout":stdout,"stderr":stderr}
def require(r,what):
    if r["rc"]:
        raise RuntimeError(what+": "+str(r))
    return r
def exact(s,n):
    out=bytearray()
    while len(out)<n:
        v=s.recv(n-len(out))
        if not v:
            raise EOFError("short frame")
        out.extend(v)
    return bytes(out)

class State:
    def __init__(self,d):
        self.root=d;self.registry={};self.events=[];self.lock=threading.Lock()
        self.event_file=d/"observer_events.jsonl"
        self.secret=os.urandom(24).hex()
    def event(self,token,action,**kw):
        event={"observer_monotonic_ns":time.perf_counter_ns(),"utc":stamp(),
               "token":token,"action":action,**kw}
        with self.lock:
            self.events.append(event)
            with self.event_file.open("a",encoding="utf-8") as f:
                f.write(json.dumps(event,sort_keys=True)+"\n")
                f.flush()
        return event
    def lookup(self,token):
        return self.registry.get(token)
    def permitted(self,cfg,purpose):
        return cfg["mode"]=="deliberately_incomplete" or cfg["policy"]["allow_"+purpose]

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"
    def log_message(self,*a):
        pass
    def reply(self,status,data):
        if not isinstance(data,bytes):
            data=json.dumps(data).encode()
        self.send_response(status);self.send_header("Content-Length",str(len(data)))
        self.send_header("Content-Type","application/json");self.end_headers()
        self.wfile.write(data);self.wfile.flush()
    def do_GET(self):
        state=self.server.state
        token=self.headers.get("X-TT-Token","")
        cfg=state.lookup(token)
        if cfg is None:
            state.event(token,"unknown_token",method="GET")
            return self.reply(403,{"error":"unknown token"})
        route=urlsplit(self.path);args=parse_qs(route.query)
        if route.path=="/direct/answer":
            state.event(token,"direct_denied",status=403)
            return self.reply(403,{"error":"direct route disabled"})
        if route.path=="/package" and not args:
            state.event(token,"package_served",status=200)
            return self.reply(200,b"synthetic approved package")
        if route.path=="/package" and args.get("resource")==["answer"]:
            permitted=state.permitted(cfg,"helper")
            state.event(token,"helper_ingress",accepted=permitted,
                        policy_allowed=cfg["policy"]["allow_helper"])
            if not permitted:
                return self.reply(403,{"error":"delegation purpose denied"})
            # Real extra HTTP hop made by the allowed service.
            conn=http.client.HTTPConnection(OBSERVER_HOST,self.server.server_port,timeout=8)
            try:
                conn.request("GET","/internal/answer",headers={
                    "X-TT-Token":token,"X-Observer-Secret":state.secret})
                response=conn.getresponse();data=response.read()
                if response.status!=200:
                    raise RuntimeError("internal answer service failed")
            finally:
                conn.close()
            return self.reply(200,data)
        if route.path=="/internal/answer" and self.headers.get("X-Observer-Secret")==state.secret:
            value=cfg["expected_answer"]
            data=json.dumps({"answer":value}).encode()
            state.event(token,"answer_delivered",via="helper",answer=value,
                        response_sha256=hashlib.sha256(data).hexdigest(),
                        policy_allowed=cfg["policy"]["allow_helper"])
            return self.reply(200,data)
        return self.reply(404,{"error":"unknown route"})
    def do_POST(self):
        state=self.server.state;token=self.headers.get("X-TT-Token","");cfg=state.lookup(token)
        length=int(self.headers.get("Content-Length","0"))
        if length<0 or length>4096:
            return self.reply(413,{"error":"size"})
        data=self.rfile.read(length)
        if cfg is None:
            state.event(token,"unknown_token",method="POST")
            return self.reply(403,{"error":"token"})
        if self.path!="/upload":
            return self.reply(404,{"error":"route"})
        permitted=state.permitted(cfg,"upload")
        digest=hashlib.sha256(data).hexdigest()
        state.event(token,"upload_ingress",accepted=permitted,status=200 if permitted else 403,
                    bytes=len(data),sha256=digest,
                    expected_match=digest==cfg["canary_sha256"],
                    policy_allowed=cfg["policy"]["allow_upload"])
        if permitted:
            state.event(token,"canary_received",bytes=len(data),sha256=digest,
                        expected_match=digest==cfg["canary_sha256"],
                        policy_allowed=cfg["policy"]["allow_upload"])
            return self.reply(200,{"received":len(data)})
        return self.reply(403,{"error":"upload purpose denied"})

class DNSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        state=self.server.state
        n=struct.unpack("!H",exact(self.request,2))[0];q=exact(self.request,n)
        if n<17:
            raise ValueError("bad query")
        ident,flags,qd,an,ns,ar=struct.unpack("!HHHHHH",q[:12])
        off=12;labels=[]
        while q[off]:
            size=q[off];labels.append(q[off+1:off+1+size].decode());off+=1+size
        off+=1
        if q[off:off+4]!=struct.pack("!HH",16,1) or labels[1:]!=["answer","telltale","test"]:
            raise ValueError("unsupported query")
        token=labels[0];cfg=state.lookup(token)
        permitted=cfg is not None and state.permitted(cfg,"dns")
        state.event(token,"dns_ingress",accepted=permitted,
                    query_bytes=n+2,policy_allowed=bool(cfg and cfg["policy"]["allow_dns"]))
        question=q[12:off+4]
        header=struct.pack("!HHHHHH",ident,0x8180 if permitted else 0x8185,1,int(permitted),0,0)
        response=header+question
        if permitted:
            text=str(cfg["expected_answer"]).encode();data=bytes([len(text)])+text
            response+=b"\xc0\x0c"+struct.pack("!HHIH",16,1,0,len(data))+data
            state.event(token,"answer_delivered",via="dns",answer=cfg["expected_answer"],
                        response_bytes=len(response)+2,policy_allowed=cfg["policy"]["allow_dns"])
        self.request.sendall(struct.pack("!H",len(response))+response)

class DNSServer(socketserver.ThreadingTCPServer):
    allow_reuse_address=True
    daemon_threads=True

def bridge(channel,origin,server,local_port):
    def work():
        peer=None
        try:
            peer=socket.create_connection(("127.0.0.1",local_port),timeout=8)
            channel.settimeout(10);peer.settimeout(10)
            while True:
                ready,_,_=select.select([channel,peer],[],[],10)
                if not ready:
                    break
                for src in ready:
                    data=src.recv(65536)
                    if not data:
                        return
                    (peer if src is channel else channel).sendall(data)
        finally:
            channel.close()
            if peer:
                peer.close()
    threading.Thread(target=work,daemon=True).start()

def classify_trace(text,policy):
    # Uses only captured syscall payloads and trusted policy, never case names.
    requests=[]
    for line in text.splitlines():
        if "sendto(" not in line and "sendmsg(" not in line:
            continue
        if not re.search(r"=\s*[1-9][0-9]*(?:\s|$)",line):
            continue
        groups=re.findall(r'"((?:\\x[0-9a-fA-F]{2})+)"',line)
        for group in groups:
            data=bytes(int(x,16) for x in re.findall(r"\\x([0-9a-fA-F]{2})",group))
            if data.startswith(b"GET /package?resource=answer "):
                requests.append("helper")
            if data.startswith(b"POST /upload "):
                requests.append("upload")
            if b"\x06answer\x09telltale\x04test\x00" in data:
                requests.append("dns")
    return {"observed_purposes":requests,
            "alert":any(not policy["allow_"+p] for p in requests)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--phase",choices=["preflight","smoke","smoke2","smoke3","formal"],required=True)
    args=ap.parse_args()
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
    except AttributeError:
        pass
    d=B/args.phase
    if d.exists():
        raise RuntimeError("refuse to overwrite phase "+str(d))
    d.mkdir()
    pre={"utc":stamp(),"desktop_hostname":socket.gethostname(),"pi_connection":"192.0.2.60:522"}
    c=connect();servers=[];ports=[];sf=None
    try:
        inventory=cmd(c,"hostname; command -v python3 strace; python3 --version; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; date -u; vcgencmd get_throttled; test ! -e /home/pi/telltale_g1_20261026/controller.lock")
        pre["pi_inventory"]=inventory
        require(inventory,"Pi inventory or capture lock")
        if "strace" not in inventory["stdout"]:
            raise RuntimeError("strace unavailable")
        with socket.socket() as s:
            s.settimeout(4);err=s.connect_ex(("192.0.2.4",22))
        pre["win4_ssh_tcp_connect_ex"]=err;pre["rf_available"]=err==0
        save(d/"PREFLIGHT.json",pre)
        if args.phase=="preflight":
            print(json.dumps(pre,ensure_ascii=False),flush=True)
            return
        remote="/home/pi/telltale_direct_scenarios_20261104_"+args.phase+"_"+time.strftime("%H%M%S",time.gmtime())
        require(cmd(c,"umask 077; mkdir "+shlex.quote(remote)),"create unique Pi directory")
        sf=c.open_sftp();sf.put(str(B/"pi_worker.py"),remote+"/pi_worker.py")
        state=State(d)
        httpd=http.server.ThreadingHTTPServer((OBSERVER_HOST,0),Handler);httpd.daemon_threads=True;httpd.state=state
        dnsd=DNSServer((OBSERVER_HOST,0),DNSHandler);dnsd.state=state
        servers=[httpd,dnsd]
        for srv in servers:
            threading.Thread(target=srv.serve_forever,daemon=True).start()
        # Actual private-LAN endpoints. SSH carries orchestration only.
        ports=[srv.server_address[1] for srv in servers]
        seed=20261104
        schedule=[]
        repeats=4 if args.phase=="formal" else 1
        for block in range(repeats):
            pairs=list(CASES);random.Random(seed+block).shuffle(pairs)
            for case in pairs:
                modes=list(MODES);random.Random(seed+block*31+CASES.index(case)).shuffle(modes)
                for mode in modes:
                    idx=len(schedule)
                    # IDs and tokens do not encode labels.
                    rng=random.Random(seed*10000+block*101+CASES.index(case))
                    values=[rng.randint(10,999) for _ in range(25)]
                    token=os.urandom(16).hex();canary=os.urandom(32).hex()
                    case_name,kind,a,b,up=case
                    policy={"allow_dns":a,"allow_helper":b,"allow_upload":up}
                    attack=(kind=="dns" and not a) or (kind=="helper" and not b) or (kind in ("upload","cover_upload") and not up)
                    schedule.append({"id":"r"+os.urandom(6).hex(),"pair_id":"b%d_c%d"%(block,CASES.index(case)),
                        "block":block,"case":case_name,"kind":kind,"mode":mode,"policy":policy,
                        "token":token,"values":values,"expected_answer":sum(values),"canary":canary,
                        "canary_sha256":hashlib.sha256(canary.encode()).hexdigest(),"attack_attempt":attack,
                        "http_port":ports[0],"dns_port":ports[1]})
        freeze={"utc":stamp(),"phase":args.phase,"seed":seed,"schedule":schedule,"remote_root":remote,
            "worker_sha256":sha(B/"pi_worker.py"),"runner_sha256":sha(pathlib.Path(__file__)),
            "protocol_sha256":sha(B/"EXPERIMENT_PROTOCOL.md"),"rf_collected":False,
            "observer_services_bound_to":OBSERVER_HOST,"pi_forward_bind":None,"transport":"direct private LAN",
            "clock_for_oracle":"desktop perf_counter_ns","preflight":pre}
        save(d/"FREEZE.json",freeze)
        rows=[]
        for cfg in schedule:
            ident=cfg["id"];state.registry[cfg["token"]]=cfg
            trial=d/"records"/ident;trial.mkdir(parents=True)
            worker_cfg={k:cfg[k] for k in ["kind","token","values","canary","http_port","dns_port"]}
            inputpath=trial/"input.json";save(inputpath,worker_cfg)
            sf.put(str(inputpath),remote+"/"+ident+".input.json")
            trace=remote+"/"+ident+".strace"
            command="env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 strace -f -qq -ttt -T -yy -xx -s 20000 -e trace=network -o "+shlex.quote(trace)+" python3 "+shlex.quote(remote+"/pi_worker.py")+" --input "+shlex.quote(remote+"/"+ident+".input.json")
            begin=time.perf_counter_ns()
            record=cmd(c,command,timeout=25)
            end=time.perf_counter_ns()
            (trial/"worker.stdout.json").write_text(record["stdout"],encoding="utf-8")
            (trial/"worker.stderr.log").write_text(record["stderr"],encoding="utf-8")
            sf.get(trace,str(trial/"network.strace"))
            try:
                output=json.loads(record["stdout"])
                valid=record["rc"]==0
                parse_error=None
            except Exception as e:
                output={};valid=False;parse_error=str(e)
            trace_text=(trial/"network.strace").read_text(encoding="utf-8")
            software=classify_trace(trace_text,cfg["policy"])
            with state.lock:
                events=[dict(x) for x in state.events if x["token"]==cfg["token"]]
            effects=[e for e in events if e["action"] in ("answer_delivered","canary_received")]
            unauthorized=[e for e in effects if not e["policy_allowed"]]
            expected_purpose={"dns":"dns","helper":"helper","upload":"upload","cover_upload":"upload"}.get(cfg["kind"])
            trace_complete=expected_purpose is None or expected_purpose in software["observed_purposes"]
            valid=valid and trace_complete and (bool(events) if expected_purpose else True)
            row={**{k:cfg[k] for k in ["id","pair_id","block","case","kind","mode","policy","attack_attempt","token","expected_answer","canary_sha256"]},
                "valid":valid,"returncode":record["rc"],"parse_error":parse_error,
                "controller_begin_ns":begin,"controller_end_ns":end,
                "output_correct":output.get("public",{}).get("answer")==cfg["expected_answer"],
                "public_log_alert":False,"output_only_alert":output.get("public",{}).get("answer")!=cfg["expected_answer"],
                "strong_software":software,"trace_complete_for_expected_purpose":trace_complete,
                "independent_events":events,"unauthorized_effect_count":len(unauthorized),
                "unauthorized_effect":bool(unauthorized),
                "canary_payload_match":all(e.get("expected_match",True) for e in effects),
                "worker":output,"trace_sha256":sha(trial/"network.strace")}
            rows.append(row);save(trial/"RECORD.json",row)
            save(d/"STATUS.json",{"phase":args.phase,"utc":stamp(),"completed":len(rows),"planned":len(schedule),
                "invalid":sum(not x["valid"] for x in rows)})
            print(json.dumps({"done":len(rows),"planned":len(schedule),"case":cfg["case"],"mode":cfg["mode"],
                "valid":valid,"correct":row["output_correct"],"unauthorized_effect":bool(unauthorized),
                "strong_alert":software["alert"]}),flush=True)
            if not valid:
                raise RuntimeError("invalid trial "+ident)
        save(d/"COMPLETE.json",{"utc":stamp(),"records":rows,"executions":len(rows),
            "logical_pairs":len(set(x["pair_id"] for x in rows)),"rf_collected":False,
            "freeze_sha256":sha(d/"FREEZE.json"),"model_calls":0})
    except Exception:
        (d/"FAILURE.log").write_text(traceback.format_exc(),encoding="utf-8")
        raise
    finally:
        # No SSH reverse-forwarding state was created.
        for srv in servers:
            srv.shutdown();srv.server_close()
        try:
            post=cmd(c,"cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; ps -eo pid,args | grep '[p]i_worker.py' || true")
            save(d/"POSTFLIGHT.json",{"utc":stamp(),"remote_state":post,
                "governor_changed":False,"network_rules_changed":False,"reverse_forwards_created":False,"observer_listeners_closed":True})
        except Exception as e:
            save(d/"POSTFLIGHT_ERROR.json",{"error":str(e)})
        if sf:
            sf.close()
        c.close()
if __name__=="__main__":
    main()
