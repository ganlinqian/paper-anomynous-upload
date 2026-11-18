import json,pathlib,subprocess,sys,time
B=pathlib.Path(__file__).resolve().parent;deadline=time.monotonic()+7200
while not (B.parent/'extension_transfer/F_UPLOAD_COMPLETE.json').exists():
 if (B.parent/'extension_transfer/FAILURE.json').exists():raise RuntimeError('F transfer failed; no capture during source reads')
 if time.monotonic()>deadline:raise TimeoutError('F reads did not finish')
 (B/'QUEUE_STATUS.json').write_text(json.dumps({'waiting_for':'F source reads to finish','utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}))
 time.sleep(15)
raise SystemExit(subprocess.run([sys.executable,'-u',str(B/'collect_confirmation.py')]).returncode)
