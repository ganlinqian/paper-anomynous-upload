import json,pathlib,subprocess,sys,time
B=pathlib.Path(__file__).resolve().parent;deadline=time.monotonic()+10800
while True:
 previous=B.parent/'burst_confirmation_study/LATEST.json';ready=False
 if previous.exists():
  d=pathlib.Path(json.loads(previous.read_text())['directory'])
  if (d/'FAILURE.log').exists():raise RuntimeError('C09 failed; preserve and review before next batch')
  ready=(d/'COMPLETE.json').exists() and (d/'POSTFLIGHT.json').exists()
 if ready and (B.parent/'wait_transfer/WAIT_UPLOAD_COMPLETE.json').exists():break
 if (B.parent/'resume_20261105_0305/FAILURE.log').exists():raise RuntimeError('resume transfer failed')
 if time.monotonic()>deadline:raise TimeoutError('C09 acquisition not complete')
 (B/'QUEUE_STATUS.json').write_text(json.dumps({'waiting_for':'C09 complete and J reads end','utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}));time.sleep(15)
raise SystemExit(subprocess.run([sys.executable,'-u',str(B/'collect_wait_confirm.py')]).returncode)
