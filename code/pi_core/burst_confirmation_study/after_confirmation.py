import json,pathlib,subprocess,sys,time
B=pathlib.Path(__file__).resolve().parent;deadline=time.monotonic()+9000
while True:
 previous=B.parent/'confirmation_study/LATEST.json';ready=False
 if previous.exists():
  d=pathlib.Path(json.loads(previous.read_text())['directory'])
  if (d/'FAILURE.log').exists():raise RuntimeError('C08 failed; preserve and review before continuing')
  ready=(d/'COMPLETE.json').exists() and (d/'POSTFLIGHT.json').exists()
 if ready and (B.parent/'wait_transfer/WAIT_UPLOAD_COMPLETE.json').exists():break
 if (B.parent/'wait_transfer/FAILURE.json').exists():raise RuntimeError('J transfer failed; no capture during source reads')
 if time.monotonic()>deadline:raise TimeoutError('waiting for C08 and J source reads')
 (B/'QUEUE_STATUS.json').write_text(json.dumps({'waiting_for':'C08 COMPLETE/POSTFLIGHT and C07 J source reads end','utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}));time.sleep(15)
raise SystemExit(subprocess.run([sys.executable,'-u',str(B/'collect_burst_confirm.py')]).returncode)
