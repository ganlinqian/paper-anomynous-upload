import csv,json,pathlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from bridge_utils import lower_priority
lower_priority();b=pathlib.Path(__file__).resolve().parent;a=b/'analysis';f=a/'matrix_features';r=json.loads((a/'MATRIX_EARLY.json').read_text());rows=[x for x in json.loads((b/'transfer/LEDGER.json').read_text())['records'] if x['stage']=='matrix'];pred={x['id']:x for x in r['predictions']};out=a/'figures';out.mkdir(exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(1,2,figsize=(10,3.7),constrained_layout=True)
for kind,color,marker in [('dns','#277da1','o'),('helper','#e76f51','s')]:
 rr=[x for x in rows if x['kind']==kind];power=[json.loads((f/(x['id']+'_930c.json')).read_text())['mean_power_db'] for x in rr];xx=[x['block']+(-.08 if x['policy_index']==0 else .08) for x in rr];ax[0].scatter(xx,power,c=color,marker=marker,label=kind,s=42,edgecolors='white',linewidths=.4)
ax[0].axvspan(2.5,4.4,color='#e8eef3',zorder=-1);ax[0].set(xlabel='Randomized block (0-2 train; 3-4 test)',ylabel='Whole-record mean received power (dB)',title='Primary 1.8 GHz channel: all 20 traces',xticks=range(5));ax[0].legend(frameon=False)
keys=['task_only','rf_only','task_plus_rf','strong_content_audit'];labels=['Task','RF','Task + RF','Content audit'];values=np.array([r[k]['accuracy'] for k in keys]);ci=np.array([r[k]['accuracy_95pct'] for k in keys]);ax[1].bar(range(4),values,color=['#b8bdc5','#809fb0','#df9a57','#7ca07d'],width=.62);ax[1].errorbar(range(4),values,yerr=np.array([values-ci[:,0],ci[:,1]-values]),fmt='none',ecolor='#303030',capsize=4);ax[1].axhline(.5,color='#555',linestyle=':',linewidth=1);ax[1].set(xticks=range(4),xticklabels=labels,ylim=(0,1.17),ylabel='Violation classification accuracy',title='Forward holdout: 8 workflows; exact 95% CI')
for i,v in enumerate(values):ax[1].text(i,v+.025,str(round(v*8))+'/8',ha='center',va='bottom',fontsize=9)
fig.savefig(out/'matrix_holdout.png',dpi=180);fig.savefig(out/'matrix_holdout.pdf');plt.close(fig)
rr=[x for x in rows if x['block']>=3];fig,axes=plt.subplots(2,4,figsize=(12,5),sharex=True,sharey=True,constrained_layout=True)
for x,ax in zip(rr,axes.ravel()):
 with np.load(f/(x['id']+'_930c.npz')) as z:ct=z['sample_counts'];pw=z['power_db'];t=(np.cumsum(ct)-ct/2)/20000000
 p=pred[x['id']];ax.plot(t,pw,color='#277da1',linewidth=.55);ax.set_title(x['kind']+' | '+('violation' if x['attack_attempt'] else 'allowed')+'\nRF+task: '+('alert' if p['fused_alert'] else 'no alert'),fontsize=9);ax.set_xlabel('Recorded IQ seconds');ax.set_ylabel('Received power (dB)')
fig.suptitle('All 8 held-out traces; record-relative time, no host-clock alignment',fontsize=12);fig.savefig(out/'matrix_all_test_traces.png',dpi=180);fig.savefig(out/'matrix_all_test_traces.pdf');plt.close(fig)
with (a/'matrix_power_records.csv').open('w',newline='') as stream:
 writer=csv.DictWriter(stream,fieldnames=['id','block','kind','policy_index','attack_attempt','mean_power_db']);writer.writeheader()
 for x in rows:writer.writerow({**{k:x[k] for k in ['id','block','kind','policy_index','attack_attempt']},'mean_power_db':json.loads((f/(x['id']+'_930c.json')).read_text())['mean_power_db']})
print(json.dumps({'plots':[str(x) for x in out.iterdir()],'rows':len(rows)}))
