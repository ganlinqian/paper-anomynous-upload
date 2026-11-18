import json,os,pathlib,sys,time,traceback
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B/'burst_study'));from bridge_utils import *
sys.path.insert(1,str(B));from collect import Rig
lower_priority();campaign='confirmrxprobe_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime());d=B/campaign;d.mkdir();w=connect('192.0.2.4','win');sf=w.open_sftp();rig=None
root='F:/Data/telltale_confirmation_20261104/'+campaign
try:
 src='F:/Data/telltale_confirmation_20261104/rig_'+campaign+'.py';sf.put(str(B/'burst_study/rig_capture.py'),src);rig=Rig(w,src,root,campaign)
 results=[]
 for n in range(3):
  ident='probe'+str(n)+os.urandom(3).hex();ready=rig.rpc({'op':'capture','id':ident,'seconds':4});out=rig.rpc({'op':'finish'});assert all(x['rc']==0 and x['bytes']==160000000 for x in out['radios'])
  for x in out['radios']:sf.get(x['log'].replace('\\','/'),str(d/(ident+'_'+x['radio']+'.rf.log')))
  results.append({'ready':ready,'result':out});save(d/'PROBE.json',{'pass':len(results)==3,'engineering_only':True,'results':results,'utc':stamp()});print(json.dumps({'completed':n+1,'pass':True,'directory':str(d)}),flush=True)
  if n<2:time.sleep(5)
except Exception:(d/'FAILURE.log').write_text(traceback.format_exc());raise
finally:
 if rig:
  try:save(d/'POSTFLIGHT.json',rig.stop())
  except Exception as e:save(d/'POSTFLIGHT.json',{'error':str(e)})
 sf.close();w.close()
