import ctypes,json,pathlib,subprocess,sys,time
b=pathlib.Path(__file__).resolve().parent;ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
latest=json.loads((b.parent/'burst_study/LATEST.json').read_text());prev=pathlib.Path(latest['directory']);deadline=time.monotonic()+3600
print('WAITING_FOR '+str(prev),flush=True)
while True:
 if (prev/'FAILURE.log').exists():raise RuntimeError('predecessor failed; inspect before continuation')
 if (prev/'COMPLETE.json').exists() and (prev/'POSTFLIGHT.json').exists():
  c=json.loads((prev/'COMPLETE.json').read_text());p=json.loads((prev/'POSTFLIGHT.json').read_text());assert c['trials']==c['valid']==48,c
  assert p['restore']['rc']==0 and p['pi_lock_release']==0 and p['rig']['rc']==0,p
  break
 if time.monotonic()>deadline:raise TimeoutError('predecessor did not complete in1h')
 time.sleep(5)
print('PREDECESSOR_COMPLETE '+str(prev),flush=True)
sys.exit(subprocess.call([sys.executable,'-u',str(b/'collect_trace.py')]))
