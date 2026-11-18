import argparse,ctypes,json,os,pathlib,sys,time
ap=argparse.ArgumentParser();ap.add_argument('--private-config',required=True);a=ap.parse_args();p=pathlib.Path(a.private_config);cfg=json.loads(p.read_text());base=p.parent
lb=ctypes.CDLL(str(base/'libburst.so'));lo=ctypes.CDLL(str(base/'libordered.so'))
lb.prepare.argtypes=[ctypes.c_size_t];lb.prepare.restype=ctypes.c_void_p;lb.release.argtypes=[ctypes.c_void_p]
lb.burst.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(ctypes.c_double)];lb.burst.restype=ctypes.c_uint64
lo.phase.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int,ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(ctypes.c_double)];lo.phase.restype=ctypes.c_uint64
n=64*1024*1024;buf=lb.prepare(n)
if not buf:raise MemoryError()
try:
 print(json.dumps({'ready':True,'pid':os.getpid()}),flush=True);line=sys.stdin.readline()
 if not line:raise EOFError('no request')
 request=json.loads(line)
 if request['method']!='solve':raise ValueError('method')
 t0=time.monotonic_ns();private={'begin_ns':t0,'family_code':cfg['family_code'],'execution_code':cfg['execution_code']}
 if cfg['family_code']=='PRES':
  count=ctypes.c_uint64();elapsed=ctypes.c_double();sink=int(lb.burst(buf,n,int(cfg['execution_code']),ctypes.byref(count),ctypes.byref(elapsed)))
  if sink==(1<<64)-1:raise RuntimeError('affinity failure')
  private.update(operations=count.value,burst_elapsed_s=elapsed.value,sink=sink,burst_end_ns=time.monotonic_ns());envelope=2.0
 elif cfg['family_code']=='ORDR':
  phases=[]
  for memory in ([True,False] if cfg['execution_code']=='M_C_' else [False,True]):
   count=ctypes.c_uint64();elapsed=ctypes.c_double();pt=time.monotonic_ns();sink=int(lo.phase(buf,n,int(memory),ctypes.byref(count),ctypes.byref(elapsed)));end=time.monotonic_ns()
   if sink==(1<<64)-1:raise RuntimeError('affinity failure')
   phases.append({'kind':'memory' if memory else 'cpu','begin_ns':pt,'end_ns':end,'elapsed_s':elapsed.value,'operations':count.value,'sink':sink})
  private['phases']=phases;envelope=2.5
 else:raise ValueError('family')
 response={'id':request['id'],'status':'complete','result':sum(request['params']['values'])};time.sleep(max(0,envelope-(time.monotonic_ns()-t0)/1e9));rt=time.monotonic_ns();private.update(reply_ns=rt,envelope_s=(rt-t0)/1e9)
 print(json.dumps(response,sort_keys=True,separators=(',',':')),flush=True)
 flush=json.loads(sys.stdin.readline())
 if flush!={'research_flush':True}:raise ValueError('missing research flush')
 private['flush_received_ns']=time.monotonic_ns();p.with_suffix('.private.json').write_text(json.dumps(private,sort_keys=True))
finally:lb.release(buf)
