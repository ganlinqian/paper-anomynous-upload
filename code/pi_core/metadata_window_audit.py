"""Posthoc descriptive metadata audit; no learned model or threshold selection."""
from pathlib import Path
import csv,datetime,hashlib,json,math,statistics
B=Path(__file__).resolve().parent
old_path=B/'analysis_extensions/full_20261105/LEDGER.json'
new_path=B/'confirmation_study/confirm_20261105_035739_c92be0/RESULTS.json'
model_path=B/'analysis_extensions/CONFIRMATION_MODELS.json'
raw_old=json.loads(old_path.read_text(encoding='utf-8-sig'))['records']
new=json.loads(new_path.read_text(encoding='utf-8-sig'))
frozen=json.loads(model_path.read_text(encoding='utf-8-sig'))
train=set(frozen['families']['trace']['training_ids'])
old=[r for r in raw_old if r['stage']=='trace']
new=[r for r in new if r['family']=='trace']
assert len(old)==20 and len(new)==40 and all(r['valid'] for r in old+new)
FS=20000000; frame=204800
def mark(r,which,radio):
 return next(x['bytes'] for x in r[which]['marks'] if x['radio']==radio)
def desc(r):
 b=mark(r,'before','930c');a=mark(r,'after','930c')
 d=mark(r,'before','16bc');e=mark(r,'after','16bc')
 return {
 'external_request_elapsed_s':(r['return_desktop_ns']-r['dispatch_desktop_ns'])/1e9,
 'win4_local_bracket_elapsed_s':(r['after']['win_mono_ns']-r['before']['win_mono_ns'])/1e9,
 'main_bracket_iq_duration_s':(a-b)/(2*FS),
 'diagnostic_bracket_iq_duration_s':(e-d)/(2*FS),
 'main_predispatch_iq_duration_s':b/(2*FS),
 'diagnostic_predispatch_iq_duration_s':d/(2*FS),
 'main_minus_diagnostic_bracket_s':((a-b)-(e-d))/(2*FS),
 'main_complete_call_frames':math.floor((a/2)/frame)-math.ceil((b/2)/frame),
 'pre_cpu_c':r['pre']['temperature']['cpu_c'],
 'pre_ddr_c':r['pre']['temperature']['ddr_c'],
 }
def physical(r):return bool(r.get('actual_condition',r.get('actual_active')))
def auc(rows,key):
 pos=[desc(r)[key] for r in rows if physical(r)]
 neg=[desc(r)[key] for r in rows if not physical(r)]
 return sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg))
def summary(rows,key):
 data={str(a):[desc(r)[key] for r in rows if physical(r)==a] for a in [False,True]}
 v=auc(rows,key)
 return {'n':len(rows),'auc_physical_positive_direction':v,'orientation_free_max_auc_posthoc':max(v,1-v),'by_actual':{k:{'min':min(x),'median':statistics.median(x),'max':max(x)} for k,x in data.items()}}
O=B/'analysis_extensions/metadata_audit_20261105';O.mkdir(exist_ok=True)
out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'posthoc descriptive scalar metadata, after seeing the new trace outcome; no fit, no threshold optimization, no multivariate-model or no-information claim','metadata_have_no_rf_amplitude_or_spectrum':True,'sources':{str(p.relative_to(B)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [old_path,new_path,model_path]},'old_train_n':12,'old_test_n':8,'new_test_n':40,'features':{}}
sets={'old_training':[r for r in old if r['id'] in train],'old_test':[r for r in old if r['id'] not in train],'new_confirmation':new}
for k in desc(old[0]):out['features'][k]={name:summary(rows,k) for name,rows in sets.items()}
p=O/'TRACE_METADATA_AUDIT.json';assert not p.exists();p.write_text(json.dumps(out,indent=2),encoding='utf-8')
with (O/'all_metadata.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['dataset','id','block','actual']+list(desc(old[0])));w.writeheader()
 for name,rows in sets.items():
  for r in rows:w.writerow(dict(dataset=name,id=r['id'],block=r['block'],actual=physical(r),**desc(r)))
lines=['# ','',out['scope'],'','AUC','', '||AUC|AUC|40AUC|40AUC|','|---|---:|---:|---:|---:|']
for k,z in out['features'].items():lines.append('|'+k+'|'+'|'.join(f"{z[s]['auc_physical_positive_direction']:.4f}" for s in sets)+f"|{z['new_confirmation']['orientation_free_max_auc_posthoc']:.4f}|")
lines+=['','win4204800RFwindowframe_checksRF','']
(O/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'new_auc':{k:z['new_confirmation']['auc_physical_positive_direction'] for k,z in out['features'].items()}},ensure_ascii=False))
