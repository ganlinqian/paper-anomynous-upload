import json,pathlib,subprocess,sys,time,traceback,paramiko
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B/'burst_study'));from bridge_utils import *
lower_priority();cfg=json.loads((B/'EXTENSION_REMOTE.json').read_text());root=cfg['remote_root'];out=B/'resume_20261105_0305';out.mkdir(exist_ok=False);c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy());c.connect(cfg['host'],port=cfg['port'],username=cfg['user'],key_filename=cfg['key'],timeout=15);sf=c.open_sftp()
try:
 groups={'F':json.loads((B/'extension_transfer/MANIFEST.json').read_text())['files'],'J':json.loads((B/'wait_transfer/MANIFEST.json').read_text())['files']};files=groups['F']+groups['J'];assert len(files)==240 and len({x['filename'] for x in files})==240
 sources={x['filename']:x for x in json.loads(sf.open(root+'/SOURCE_RECEIPTS.json').read())['files']};complete=set();verified=[]
 for row in files:
  name=row['filename'];path=root+'/raw/'+name
  try:stat=sf.stat(path)
  except OSError:continue
  assert stat.st_size==row['expected_bytes']
  try:receipt=json.loads(sf.open(root+'/features/'+name[:-3]+'.json').read());hs=receipt['raw_sha256']
  except OSError:hs=run(c,'sha256sum '+path,timeout=60)['stdout'].split()[0]
  assert hs==sources[name]['sha256'];complete.add(name);verified.append({'filename':name,'sha256':hs,'bytes':stat.st_size})
 save(out/'EXISTING_VALIDATED.json',{'files':verified,'count':len(complete),'utc':stamp()})
 remaining=[x for x in files if x['filename'] not in complete];remaining.sort(key=lambda x:(0 if x['stage']=='wait' and x['radio']=='930c' else 1 if x['stage']!='wait' else 2,x['filename']))
 start=time.monotonic()
 for idx,row in enumerate(remaining):
  path=root+'/raw/'+row['filename'];cmd=['scp','-q','-3','-X','nrequests=256','-X','buffer=131072','-o','Compression=no','-F',str(B/'extension_ssh_config'),'claw-rig-ext:'+row['source_raw'],'claw-cpu-ext:'+path+'.resume20261105.partial']
  with (out/'scp.log').open('ab') as log:ret=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=240)
  if ret.returncode:raise RuntimeError('scp rc='+str(ret.returncode)+' '+row['filename'])
  assert sf.stat(path+'.resume20261105.partial').st_size==row['expected_bytes'];sf.posix_rename(path+'.resume20261105.partial',path);complete.add(row['filename']);save(out/'STATUS.json',{'completed':len(complete),'planned':240,'resumed_uploaded':idx+1,'elapsed_s':time.monotonic()-start,'utc':stamp()});print(json.dumps({'completed':len(complete),'stage':row['stage'],'radio':row['radio'],'utc':stamp()}),flush=True)
  for drive,folder,marker in [('F','extension_transfer','F_UPLOAD_COMPLETE.json'),('J','wait_transfer','WAIT_UPLOAD_COMPLETE.json')]:
   if not (B/folder/marker).exists() and all(x['filename'] in complete for x in groups[drive]):
    m={'expected_files':len(groups[drive]),'bytes':sum(x['expected_bytes'] for x in groups[drive]),'utc':stamp(),'resumed':True};save(B/folder/marker,m);sf.put(str(B/folder/marker),root+'/'+marker)
 assert len(complete)==240;m={'expected_files':240,'bytes':sum(x['expected_bytes'] for x in files),'utc':stamp(),'resumed':True};save(out/'UPLOAD_COMPLETE.json',m);sf.put(str(out/'UPLOAD_COMPLETE.json'),root+'/UPLOAD_COMPLETE.json');print(json.dumps(m),flush=True)
except Exception:(out/'FAILURE.log').write_text(traceback.format_exc());raise
finally:sf.close();c.close()
