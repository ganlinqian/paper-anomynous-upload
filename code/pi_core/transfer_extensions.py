import json,pathlib,subprocess,time,traceback
import paramiko
from bridge_utils import *
b=pathlib.Path(__file__).resolve().parent;lower_priority();cfg=json.loads((b/'EXTENSION_REMOTE.json').read_text());root=cfg['remote_root'];out=b/'extension_transfer';assert not (out/'STATUS.json').exists();files=json.loads((out/'MANIFEST.json').read_text())['files'];c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp();config=b/'extension_ssh_config';config.write_text('Host claw-rig-ext\n HostName 192.0.2.4\n User win\n Port 22\n IdentityFile <SSH_KEY>\n StrictHostKeyChecking yes\n Compression no\nHost claw-cpu-ext\n HostName '+cfg['host']+'\n User '+cfg['user']+'\n Port '+str(cfg['port'])+'\n IdentityFile '+cfg['key']+'\n StrictHostKeyChecking yes\n Compression no\n')
try:
 start=time.monotonic();total=0
 with (out/'scp.log').open('wb') as log:
  for i,row in enumerate(files):
   cmd=['scp','-q','-3','-X','nrequests=256','-X','buffer=131072','-o','Compression=no','-F',str(config),'claw-rig-ext:'+row['source_raw'],'claw-cpu-ext:'+root+'/raw/'+row['filename']+'.partial'];ret=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=180)
   if ret.returncode:raise RuntimeError('scp '+row['filename']+' rc='+str(ret.returncode))
   remote=root+'/raw/'+row['filename'];assert sf.stat(remote+'.partial').st_size==row['expected_bytes'];sf.rename(remote+'.partial',remote);total+=row['expected_bytes'];save(out/'STATUS.json',{'completed':i+1,'planned':len(files),'bytes':total,'elapsed_s':time.monotonic()-start,'utc':stamp()});print(json.dumps({'completed':i+1,'planned':len(files),'stage':row['stage'],'radio':row['radio'],'elapsed_s':time.monotonic()-start}),flush=True)
 marker={'expected_files':len(files),'bytes':total,'utc':stamp()};save(out/'F_UPLOAD_COMPLETE.json',marker);sf.put(str(out/'F_UPLOAD_COMPLETE.json'),root+'/F_UPLOAD_COMPLETE.json');print(json.dumps(marker),flush=True)
except Exception:(out/'TRANSFER_FAILURE.log').write_text(traceback.format_exc());raise
finally:sf.close();c.close()
