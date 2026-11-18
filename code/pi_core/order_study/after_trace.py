import ctypes,json,pathlib,subprocess,sys,time
b=pathlib.Path(__file__).resolve().parent;ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000);lp=b.parent/'complete_trace_study/LATEST.json';deadline=time.monotonic()+5400;prev=None
print('WAITING_FOR_COMPLETE_TRACE',flush=True)
while True:
 if prev is None and lp.exists():prev=pathlib.Path(json.loads(lp.read_text())['directory']);print('PREDECESSOR '+str(prev),flush=True)
 if prev is not None:
  if (prev/'FAILURE.log').exists():raise RuntimeError('predecessor failed; inspect before continuation')
  if (prev/'COMPLETE.json').exists() and (prev/'POSTFLIGHT.json').exists():
   c=json.loads((prev/'COMPLETE.json').read_text());p=json.loads((prev/'POSTFLIGHT.json').read_text());assert c['trials']==c['valid']==20,c;assert p['restore']['rc']==0 and p['pi_lock_release']==0 and p['rig']['rc']==0,p;break
 if time.monotonic()>deadline:raise TimeoutError('predecessor not completed in90min')
 time.sleep(5)
print('PREDECESSOR_COMPLETE '+str(prev),flush=True);sys.exit(subprocess.call([sys.executable,'-u',str(b/'collect_order.py')]))
