import argparse,json,pathlib
from remote_extensions import conditioned,burst
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--stage',choices=['trace','order','burst'],required=True);a=ap.parse_args();root=pathlib.Path(a.root);rows=[x for x in json.loads((root/'LEDGER.json').read_text())['records'] if x['stage']==a.stage];sources={x['filename']:x for x in json.loads((root/'SOURCE_RECEIPTS.json').read_text())['files']}
for row in rows:
 name=row['id']+'_930c.iq';receipt=json.loads((root/'features'/(row['id']+'_930c.json')).read_text());assert receipt['raw_sha256']==sources[name]['sha256'] and receipt['raw_bytes']==sources[name]['bytes'] and receipt['full_contiguous']
result=burst(root,rows) if a.stage=='burst' else conditioned(root,rows,a.stage=='order');result['verified_primary_files']=len(rows);path=root/(a.stage.upper()+'_EARLY.json');path.write_text(json.dumps(result,indent=2))
if a.stage=='burst':print(json.dumps({'stage':a.stage,'activity':result['activity']}))
else:print(json.dumps({'stage':a.stage,'models':{k:v['task_plus_rf'] for k,v in result['models'].items()},'timing_with_task':result['external_elapsed_time']['with_task']}))
