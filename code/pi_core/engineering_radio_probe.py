import argparse,json,os,pathlib,re,sys,time,traceback
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B/'burst_study'));from bridge_utils import *
sys.path.insert(1,str(B));from collect import Rig
ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['main_only','diag_only','stagger','simultaneous'],required=True);a=ap.parse_args()
lower_priority();campaign='radioeng_'+a.variant+'_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime());d=B/campaign;d.mkdir();w=connect('192.0.2.4','win');sf=w.open_sftp();rig=None
base=(B/'burst_study/rig_capture.py').read_text();src=base
if a.variant=='main_only':src=re.sub(r'^RADIOS=.*$', 'RADIOS=[("930c","<hackrf-serial>",1800000000)]',src,count=1,flags=re.M)
if a.variant=='diag_only':src=re.sub(r'^RADIOS=.*$', 'RADIOS=[("16bc","<hackrf-serial>",105000000)]',src,count=1,flags=re.M)
if a.variant=='stagger':
 needle='                until=time.monotonic()+5'
 target='                    if len(active)==1:time.sleep(0.25)\n'+needle
 assert src.count(needle)==1;src=src.replace(needle,target)
(d/'rig_probe_source.py').write_text(src)
root='F:/Data/telltale_confirmation_20261104/'+campaign
try:
 rs='F:/Data/telltale_confirmation_20261104/rig_'+campaign+'.py';sf.put(str(d/'rig_probe_source.py'),rs);rig=Rig(w,rs,root,campaign)
 ident='engineering'+os.urandom(4).hex();ready=rig.rpc({'op':'capture','id':ident,'seconds':4});out=rig.rpc({'op':'finish'})
 for x in out['radios']:sf.get(x['log'].replace('\\','/'),str(d/(x['radio']+'.rf.log')))
 passed=all(x['rc']==0 and x['bytes']==160000000 for x in out['radios']);save(d/'PROBE.json',{'pass':passed,'engineering_only':True,'variant':a.variant,'source_sha256':sha(d/'rig_probe_source.py'),'ready':ready,'result':out,'utc':stamp()});print(json.dumps({'pass':passed,'variant':a.variant,'directory':str(d)}))
 if not passed:raise RuntimeError('probe invalid')
except Exception:
 (d/'FAILURE.log').write_text(traceback.format_exc())
 for x in sf.listdir_attr(root):
  if x.filename.endswith('.log'):sf.get(root+'/'+x.filename,str(d/x.filename))
 print(json.dumps({'pass':False,'variant':a.variant,'directory':str(d),'logs':{p.name:p.read_text(errors='replace')[-300:] for p in d.glob('*.log')}}));raise
finally:
 if rig:
  try:save(d/'POSTFLIGHT.json',rig.stop())
  except Exception as e:save(d/'POSTFLIGHT.json',{'error':str(e)})
 sf.close();w.close()
