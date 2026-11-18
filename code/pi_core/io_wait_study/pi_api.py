import argparse,hashlib,http.client,json,os,pathlib,signal,subprocess,sys,threading,time

def stop_owned(signum,frame):raise SystemExit(128+signum)
signal.signal(signal.SIGTERM,stop_owned)
signal.signal(signal.SIGINT,stop_owned)
ap=argparse.ArgumentParser();ap.add_argument('--private-config',required=True);a=ap.parse_args();p=pathlib.Path(a.private_config);cfg=json.loads(p.read_text());warm=pathlib.Path(cfg['input_path']).read_bytes();assert hashlib.sha256(warm).hexdigest()==cfg['input_sha256'];out=open(cfg['output_path'],'xb');task=None;archive={};monitor=None
try:
 print(json.dumps({'ready':True,'pid':os.getpid(),'input_sha256':cfg['input_sha256']}),flush=True);line=sys.stdin.readline()
 if not line:raise EOFError('no request')
 request=json.loads(line);assert request['method']=='solve';begin=time.monotonic_ns();c=http.client.HTTPConnection('192.0.2.39',cfg['port'],timeout=8);c.request('GET','/approved/package',headers={'X-TT-Token':request['id']});sent=time.monotonic_ns()
 if cfg['activity_code']=='A___':
  archive['begin_ns']=time.monotonic_ns();task=subprocess.Popen(['taskset','-c','3','nice','-n','10','gzip','-n','-1','-c',cfg['input_path']],stdout=out,stderr=subprocess.PIPE)
  def finish_archive():
   try:
    archive['returncode']=task.wait(timeout=7);archive['stderr']=task.stderr.read().decode('utf-8','replace');archive['process_end_ns']=time.monotonic_ns();os.fsync(out.fileno());archive['fsync_end_ns']=time.monotonic_ns()
   except BaseException as exc:archive['error']=repr(exc)
  monitor=threading.Thread(target=finish_archive);monitor.start()
 response=c.getresponse();body=response.read();received=time.monotonic_ns();c.close();assert response.status==200;values=json.loads(body)['values'];assert values==request['params']['values']
 if monitor:monitor.join(8)
 if monitor and monitor.is_alive():raise TimeoutError('archive did not finish')
 if task and (archive.get('returncode')!=0 or archive.get('stderr','').strip() or archive.get('error')):raise RuntimeError('gzip failure '+str(archive))
 public={'id':request['id'],'status':'complete','result':sum(values)};reply=time.monotonic_ns();print(json.dumps(public,sort_keys=True,separators=(',',':')),flush=True)
 flush=sys.stdin.readline()
 if not flush or not json.loads(flush).get('research_flush'):raise EOFError('no research flush')
 private={'begin_ns':begin,'http_sent_ns':sent,'http_received_ns':received,'reply_ns':reply,'archive':archive,'activity_code':cfg['activity_code'],'output_bytes':os.fstat(out.fileno()).st_size,'archive_inside_wait':bool(archive and sent<=archive['begin_ns']<archive['fsync_end_ns']<=received)};p.with_suffix('.private.json').write_text(json.dumps(private,sort_keys=True))
finally:
 if task and task.poll() is None:task.terminate();task.wait(timeout=5)
 out.close()
