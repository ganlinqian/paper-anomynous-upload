import argparse,ctypes,json,os,pathlib,sys,time
ap=argparse.ArgumentParser();ap.add_argument('--private-config',required=True);a=ap.parse_args();p=pathlib.Path(a.private_config);cfg=json.loads(p.read_text());lib=ctypes.CDLL(str(p.parent/'libordered.so'));lib.prepare.argtypes=[ctypes.c_size_t];lib.prepare.restype=ctypes.c_void_p;lib.phase.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int,ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(ctypes.c_double)];lib.phase.restype=ctypes.c_uint64;lib.release.argtypes=[ctypes.c_void_p];n=64*1024*1024;buf=lib.prepare(n)
if not buf:raise MemoryError()
try:
 print(json.dumps({'ready':True,'pid':os.getpid()}),flush=True);line=sys.stdin.readline()
 if not line:raise EOFError('no request')
 request=json.loads(line)
 if request['method']!='solve':raise ValueError('method')
 t0=time.monotonic_ns();phases=[]
 for mem in ([True,False] if cfg['order_code']=='M_C_' else [False,True]):
  count=ctypes.c_uint64();elapsed=ctypes.c_double();pt=time.monotonic_ns();sink=int(lib.phase(buf,n,int(mem),ctypes.byref(count),ctypes.byref(elapsed)));end=time.monotonic_ns()
  if sink==(1<<64)-1:raise RuntimeError('affinity failure')
  phases.append({'kind':'memory' if mem else 'cpu','begin_ns':pt,'end_ns':end,'elapsed_s':elapsed.value,'operations':count.value,'sink':sink})
 response={'id':request['id'],'status':'complete','result':sum(request['params']['values'])};time.sleep(max(0,2.5-(time.monotonic_ns()-t0)/1e9));rt=time.monotonic_ns();print(json.dumps(response,sort_keys=True,separators=(',',':')),flush=True);p.with_suffix('.private.json').write_text(json.dumps({'begin_ns':t0,'reply_ns':rt,'envelope_s':(rt-t0)/1e9,'phases':phases,'order_code':cfg['order_code']},sort_keys=True))
finally:lib.release(buf)
