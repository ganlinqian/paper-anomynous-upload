import base64, ctypes, hashlib, json, os, pathlib, socket, struct, time
import paramiko
def stamp():return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def save(p,x):
    p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8");tmp.replace(p)
def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open("rb") as f:
        for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
    return h.hexdigest()
def connect(host,user,port=22):
    c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy())
    c.connect(host,port=port,username=user,key_filename=os.path.expanduser("~/.ssh/<KEY>"),timeout=12)
    return c
def run(c,s,timeout=30,check=True):
    _,o,e=c.exec_command(s,timeout=timeout);so=o.read().decode("utf-8","replace");se=e.read().decode("utf-8","replace");rc=o.channel.recv_exit_status()
    if rc and check:raise RuntimeError("rc="+str(rc)+" "+so+" "+se)
    return {"rc":rc,"stdout":so,"stderr":se}
def snapshot(c):return run(c,"cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq; vcgencmd get_throttled; vcgencmd measure_temp; ip -br addr")["stdout"]
def thermal():
    def exact(s,n):
        b=b""
        while len(b)<n:
            x=s.recv(n-len(b))
            if not x:raise RuntimeError("short Modbus")
            b+=x
        return b
    with socket.create_connection(("192.0.2.60",1502),timeout=5) as s:
        s.sendall(struct.pack(">HHHBBHH",1,0,6,1,3,0,4));hdr=exact(s,7);body=exact(s,struct.unpack(">HHHB",hdr)[2]-1)
    if body[:2]!=bytes([3,8]):raise RuntimeError("bad Modbus")
    r=struct.unpack(">4H",body[2:]);return {"cpu_c":r[1]/100,"ddr_c":r[3]/100}
def guard(p):
    state=snapshot(p);temp=thermal()
    if int(state.split("throttled=")[1].splitlines()[0],16)&15:raise RuntimeError("current throttling")
    if temp["cpu_c"]>48 or temp["ddr_c"]>43:raise RuntimeError("thermal precondition "+str(temp))
    return {"state":state,"temperature":temp}
def lower_priority():
    try:ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
    except AttributeError:pass
