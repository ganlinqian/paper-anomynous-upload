"""Exploratory diagnostic-channel audit, after primary results. No primary model changes."""
import json,pathlib,time,numpy as np
from remote_extensions import model,stats
r=pathlib.Path(__file__).resolve().parent
rows=json.loads((r/'LEDGER.json').read_text())['records']
def features(x,radio,temporal):
    with np.load(r/'features'/(x['id']+'_'+radio+'.npz')) as f:
        if not temporal:return f['features'].copy()
        w=f['sample_counts'];t=(np.cumsum(w)-w/2)/w.sum();v=[];p=[]
        for k in range(4):
            m=(t>=k/4)&(t<(k+1)/4)
            v.extend((10*np.log10(np.maximum(np.average(10**(f['band_db'][m]/10),axis=0,weights=w[m]),1e-20))).tolist())
            p.append(float(10*np.log10(np.average(10**(f['power_db'][m]/10),weights=w[m]))))
        return np.array(v+p)
out={'scope':'post hoc channel specificity audit; 105MHz channel is not assumed a physical null; no tuning or selection of primary detector','utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'stages':{}}
for stage in ('trace','order','wait','burst'):
    rr=[x for x in rows if x['stage']==stage];tr=np.array([x['block']<(4 if stage=='wait' else 2 if stage=='burst' else 3) for x in rr]);te=~tr
    actual=np.array([x['milliseconds']>0 if stage=='burst' else x['actual_order' if stage=='order' else 'actual_active'] for x in rr])
    expected=np.zeros(len(rr),dtype=bool) if stage=='burst' else np.array([x['expected_order' if stage=='order' else 'expected_active'] for x in rr])
    y=actual!=expected;z={'n_train':int(tr.sum()),'n_test':int(te.sum()),'channels':{}}
    for radio in ('930c','16bc'):
        ch={}
        for temporal in (False,True):
            X=np.array([features(x,radio,temporal) for x in rr]);m=model(stage=='burst').fit(X[tr],actual[tr]);pr=m.predict(X[te]);q=m.predict_proba(X[te])[:,1]
            ch['temporal_260' if temporal else 'whole_260']={'physical':stats(actual[te],pr,q),'task_conditioned':stats(y[te],pr!=expected[te],np.where(expected[te],1-q,q)),'predictions':[{'id':x['id'],'block':x['block'],'actual':bool(ac),'expected':bool(ex),'p_actual':float(p),'alert':bool(al)} for x,ac,ex,p,al in zip([x for x,k in zip(rr,te) if k],actual[te],expected[te],q,pr!=expected[te])]}
        z['channels'][radio]=ch
    out['stages'][stage]=z
(r/'CHANNEL_AUDIT.json').write_text(json.dumps(out,indent=2))
print(json.dumps({s:{ch:{k:v['task_conditioned'] for k,v in m.items()} for ch,m in z['channels'].items()} for s,z in out['stages'].items()}))
