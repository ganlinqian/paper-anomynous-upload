import json,pathlib,sys,paramiko
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B/'burst_study'));from bridge_utils import *
lower_priority();cfg=json.loads((B/'EXTENSION_REMOTE.json').read_text());out={'utc':stamp()}
for name,host,user,port,key in [('cpu',cfg['host'],cfg['user'],cfg['port'],cfg['key']),('capture-pc','192.0.2.4','win',22,None),('pi','192.0.2.60','admin',522,None)]:
 c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy())
 try:
  c.connect(host,port=port,username=user,key_filename=key or str(pathlib.Path.home()/'.ssh/<KEY>'),timeout=12)
  if name=='cpu':
   cmd='hostname; ps -p 412909 -o pid,args; ls '+cfg['remote_root']+'/EXTRACTION*; tail -n 2 '+cfg['remote_root']+'/extract.log';out[name]=run(c,cmd,check=False)
   sf=c.open_sftp();root=cfg['remote_root'];out['cpu_raw_files']=len([x for x in sf.listdir(root+'/raw') if x.endswith('.iq')]);out['cpu_feature_files']=len([x for x in sf.listdir(root+'/features') if x.endswith('.npz')]);sf.close()
  elif name=='pi':out[name]=run(c,'pgrep -af "python3.*telltale|hackrf|resident_tool" || true; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq; test ! -e /home/pi/telltale_g1_20261026/controller.lock; echo lock_absence_rc=$?',check=False)
  else:out[name]=run(c,'powershell -NoProfile -Command "Get-Process hackrf_transfer,python -ErrorAction SilentlyContinue | Select-Object Id,ProcessName; Get-PSDrive F,J | Select-Object Name,Free | ConvertTo-Json -Compress"',check=False)
 except Exception as e:out[name]={'error':str(e)}
 finally:c.close()
save(B/'RESUME_20261105_0304.json',out);print(json.dumps(out))
