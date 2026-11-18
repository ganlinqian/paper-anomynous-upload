"""Wait for disk/receiver handoff; never counts queued work as acquired."""
import datetime,json,pathlib,subprocess,sys,time,traceback
B=pathlib.Path(__file__).resolve().parent;P=B.parent/'confirmation_processing_20261105'
def save(x):(B/'QUEUE_STATUS.json').write_text(json.dumps(x,indent=2),encoding='utf-8')
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
deadline=time.monotonic()+10800
try:
 while True:
  if (P/'FAILURE.log').exists():raise RuntimeError('main controller failed; inspect preserved failure before shared-disk handoff')
  q=B.parent/'wait_confirmation_study/LATEST.json';ready=False
  if q.exists():
   d=pathlib.Path(json.loads(q.read_text())['directory'])
   if (d/'FAILURE.log').exists():raise RuntimeError('C10 failed; inspect preserved failure')
   if (d/'COMPLETE.json').exists() and (d/'POSTFLIGHT.json').exists():
    post=json.loads((d/'POSTFLIGHT.json').read_text())
    assert post['restore']['rc']==0 and post['pi_lock_release']==0
    ready=(P/'F_UPLOAD_COMPLETE.json').exists() and (P/'J/HASH_COMPLETE.json').exists()
  if ready:break
  if time.monotonic()>deadline:raise TimeoutError('handoff not complete within3h; no receiver started')
  save({'phase':'waiting_C10_F_upload_and_J_hash','utc':stamp(),'pid':__import__('os').getpid()});time.sleep(20)
 save({'phase':'starting_untraced_32','utc':stamp(),'pid':__import__('os').getpid()})
 z=subprocess.run([sys.executable,'-u',str(B/'collect_untraced_wait.py')])
 save({'phase':'collector_returned','utc':stamp(),'returncode':z.returncode});raise SystemExit(z.returncode)
except Exception:
 (B/'QUEUE_FAILURE.log').write_text(traceback.format_exc(),encoding='utf-8');raise
