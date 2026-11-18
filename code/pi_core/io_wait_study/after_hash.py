import ctypes,json,pathlib,subprocess,sys,time
b=pathlib.Path(__file__).resolve().parent;ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000);deadline=time.monotonic()+1800
print('WAITING_FOR_J_SOURCE_UPLOAD_AND_F_HASH',flush=True)
while not ((b.parent/'transfer/UPLOAD_COMPLETE.json').exists() and (b.parent/'extension_transfer/HASH_COMPLETE.json').exists()):
 if (b.parent/'extension_transfer/FAILURE.log').exists() or (b.parent/'transfer/FAILURE.log').exists():raise RuntimeError('source preparation failed')
 if time.monotonic()>deadline:raise TimeoutError('source gates not ready in30min')
 time.sleep(5)
print('SOURCE_GATES_READY',flush=True);sys.exit(subprocess.call([sys.executable,'-u',str(b/'collect_wait.py')]))
