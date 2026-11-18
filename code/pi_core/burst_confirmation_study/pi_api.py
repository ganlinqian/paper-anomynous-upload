import argparse,ctypes,hashlib,json,os,pathlib,sys,threading,time
ap=argparse.ArgumentParser();ap.add_argument('--private-config',required=True);a=ap.parse_args();p=pathlib.Path(a.private_config);cfg=json.loads(p.read_text());lib=ctypes.CDLL(str(p.parent/'libburst.so'))
lib.prepare.argtypes=[ctypes.c_size_t];lib.prepare.restype=ctypes.c_void_p;lib.release.argtypes=[ctypes.c_void_p];lib.burst.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(ctypes.c_double)];lib.burst.restype=ctypes.c_uint64
n=64*1024*1024;buf=lib.prepare(n);block=b'C'*1048576;cover={};ready=threading.Event()
if not buf:raise MemoryError()
def cover_work():
 os.sched_setaffinity(0,{2});cover['begin_ns']=time.monotonic_ns();ready.set();h=hashlib.sha256()
 for _ in range(64):h.update(block)
 cover.update(sha256=h.hexdigest(),end_ns=time.monotonic_ns())
try:
 print(json.dumps({'ready':True,'pid':os.getpid()}),flush=True);line=sys.stdin.readline()
 if not line:raise EOFError('no request')
 request=json.loads(line)
 if request['method']!='solve':raise ValueError('method')
 t0=time.monotonic_ns();thread=None
 if cfg['cover_code']=='YES_':
  thread=threading.Thread(target=cover_work);thread.start()
  if not ready.wait(2):raise TimeoutError('cover start')
 count=ctypes.c_uint64();elapsed=ctypes.c_double();bt=time.monotonic_ns();sink=int(lib.burst(buf,n,int(cfg['execution_code']),ctypes.byref(count),ctypes.byref(elapsed)));end=time.monotonic_ns()
 if sink==(1<<64)-1:raise RuntimeError('affinity failure')
 if thread:
  thread.join(3)
  if thread.is_alive():raise TimeoutError('cover did not finish')
 private={'begin_ns':t0,'burst_begin_ns':bt,'burst_end_ns':end,'operations':count.value,'burst_elapsed_s':elapsed.value,'sink':sink,'cover':cover,'execution_code':cfg['execution_code']}
 response={'id':request['id'],'status':'complete','result':sum(request['params']['values'])};time.sleep(max(0,2.0-(time.monotonic_ns()-t0)/1e9));rt=time.monotonic_ns();private.update(reply_ns=rt,envelope_s=(rt-t0)/1e9)
 print(json.dumps(response,sort_keys=True,separators=(',',':')),flush=True)
 if json.loads(sys.stdin.readline())!={'research_flush':True}:raise ValueError('missing flush')
 private['flush_received_ns']=time.monotonic_ns();p.with_suffix('.private.json').write_text(json.dumps(private,sort_keys=True))
finally:lib.release(buf)
