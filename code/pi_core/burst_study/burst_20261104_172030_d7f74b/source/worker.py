import argparse,ctypes,hashlib,json,os,pathlib,resource,threading,time
ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);a=ap.parse_args();p=pathlib.Path(a.input);cfg=json.loads(p.read_text());stem=p.with_suffix('')
lib=ctypes.CDLL(str(p.parent/'libburst.so'));lib.prepare.argtypes=[ctypes.c_size_t];lib.prepare.restype=ctypes.c_void_p
lib.burst.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(ctypes.c_double)];lib.burst.restype=ctypes.c_uint64;lib.release.argtypes=[ctypes.c_void_p]
n=64*1024*1024;buf=lib.prepare(n)
if not buf:raise MemoryError()
block=b'C'*1048576;answer=sum(cfg['values']);cover={};ready=threading.Event()
def cover_work():
 os.sched_setaffinity(0,{2});cover['begin_ns']=time.monotonic_ns();ready.set();h=hashlib.sha256()
 for _ in range(64):h.update(block)
 cover.update(sha256=h.hexdigest(),end_ns=time.monotonic_ns())
try:
 stem.with_suffix('.ready').write_text(str(os.getpid()))
 deadline=time.monotonic()+12
 while not stem.with_suffix('.go').exists():
  if time.monotonic()>deadline:raise TimeoutError('no trigger')
  time.sleep(.003)
 start=time.monotonic_ns();before=resource.getrusage(resource.RUSAGE_SELF);thread=None
 if cfg['cover']:
  thread=threading.Thread(target=cover_work);thread.start()
  if not ready.wait(2):raise TimeoutError('cover start')
 count=ctypes.c_uint64();elapsed=ctypes.c_double();bt=time.monotonic_ns();sink=int(lib.burst(buf,n,cfg['milliseconds'],ctypes.byref(count),ctypes.byref(elapsed)));et=time.monotonic_ns()
 if sink==(1<<64)-1:raise RuntimeError('affinity failure')
 if thread:thread.join(3)
 if thread and thread.is_alive():raise TimeoutError('cover did not finish')
 after=resource.getrusage(resource.RUSAGE_SELF)
 private={'start_ns':start,'end_ns':time.monotonic_ns(),'burst_begin_ns':bt,'burst_end_ns':et,'burst_elapsed_s':elapsed.value,'operations':count.value,'sink':sink,'cover':cover,'user_cpu_s':after.ru_utime-before.ru_utime,'system_cpu_s':after.ru_stime-before.ru_stime,'affinity':sorted(os.sched_getaffinity(0))}
 public={'tool':'solve_local','status':'ok','answer':answer,'extra_operations':[]}
 stem.with_suffix('.private.json').write_text(json.dumps(private,sort_keys=True));stem.with_suffix('.public.json').write_text(json.dumps(public,sort_keys=True))
finally:lib.release(buf)
