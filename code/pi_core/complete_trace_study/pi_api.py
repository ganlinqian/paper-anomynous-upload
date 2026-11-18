"""Single-request lab API worker. Private instrumentation is research truth, not detector input."""
import argparse,ctypes,json,os,pathlib,sys,time
ap=argparse.ArgumentParser();ap.add_argument('--private-config',required=True);a=ap.parse_args();p=pathlib.Path(a.private_config);cfg=json.loads(p.read_text());lib=ctypes.CDLL(str(p.parent/'libburst.so'))
lib.prepare.argtypes=[ctypes.c_size_t];lib.prepare.restype=ctypes.c_void_p;lib.burst.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(ctypes.c_double)];lib.burst.restype=ctypes.c_uint64;lib.release.argtypes=[ctypes.c_void_p]
n=64*1024*1024;buf=lib.prepare(n)
if not buf:raise MemoryError()
try:
 print(json.dumps({'ready':True,'pid':os.getpid()}),flush=True)
 line=sys.stdin.readline()
 if not line:raise EOFError('no request')
 request=json.loads(line)
 if request['method']!='solve':raise ValueError('method')
 t0=time.monotonic_ns();count=ctypes.c_uint64();elapsed=ctypes.c_double();sink=int(lib.burst(buf,n,int(cfg['duration_code']),ctypes.byref(count),ctypes.byref(elapsed)));bt=time.monotonic_ns()
 if sink==(1<<64)-1:raise RuntimeError('affinity failure')
 response={'id':request['id'],'status':'complete','result':sum(request['params']['values'])}
 time.sleep(max(0,2.0-(time.monotonic_ns()-t0)/1e9));rt=time.monotonic_ns();print(json.dumps(response,sort_keys=True,separators=(',',':')),flush=True)
 private={'begin_ns':t0,'burst_end_ns':bt,'reply_ns':rt,'burst_elapsed_s':elapsed.value,'operations':count.value,'sink':sink,'envelope_s':(rt-t0)/1e9,'duration_code':cfg['duration_code']}
 p.with_suffix('.private.json').write_text(json.dumps(private,sort_keys=True))
finally:lib.release(buf)
