import csv,hashlib,json,pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
B=pathlib.Path(__file__).resolve().parent;d=json.loads((B/'WAIT_EARLY.json').read_text());receipt=json.loads((B/'WAIT_RECEIPT.json').read_text());assert hashlib.sha256((B/'WAIT_EARLY.json').read_bytes()).hexdigest()==receipt['sha256']
rf=d['models']['whole_260']['predictions'];ti={x['id']:x for x in d['timing']['both_external_times']['predictions']};obs={x['id']:x for x in d['all_trial_observations']};rows=[]
for i,x in enumerate(rf):
 t=ti[x['id']];r=obs[x['id']];rows.append({'index':i+1,'id':x['id'],'block':r['block'],'actual_archive':x['actual'],'expected_archive':x['expected'],'violation':x['attack'],'rf_p_actual':x['p_actual'],'time_p_actual':t['p_actual'],'rf_p_violation':x['p_attack'],'time_p_violation':t['p_attack'],'coordinator_elapsed_s':r['coordinator_elapsed_s'],'gateway_service_s':r['gateway_service_s']})
out=B/'figures';out.mkdir(exist_ok=True)
with (out/'wait_all_test_trials.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
fig,axes=plt.subplots(2,1,figsize=(11,6.8),sharex=True,constrained_layout=True)
for ax,key,target,title in [(axes[0],'actual','actual_archive','Physical archive activity'),(axes[1],'violation','violation','Task-conditioned violation')]:
 for i,r in enumerate(rows):
  color='#b24c40' if r[target] else '#286b8e';ax.scatter(i+1,r['rf_p_'+key],color=color,marker='o',s=49,zorder=3);ax.scatter(i+1,r['time_p_'+key],color=color,marker='x',s=52,zorder=3)
 ax.axhline(.5,color='.5',ls='--',lw=.8);ax.set_ylim(-.05,1.05);ax.set_ylabel('Predicted probability');ax.set_title(title,loc='left',fontsize=11);ax.grid(axis='y',alpha=.2)
 for k in (4.5,8.5,12.5):ax.axvline(k,color='.85',lw=.7)
axes[0].plot([],[],marker='o',ls='',color='.3',label='RF, frozen whole-record model');axes[0].plot([],[],marker='x',ls='',color='.3',label='External two-time baseline');axes[0].legend(loc='center left',bbox_to_anchor=(1,.5),fontsize=8)
axes[1].set_xticks(range(1,17));axes[1].set_xlabel('All 16 held-out trials in acquisition order (four blocks)')
fig.suptitle('Real gzip during an approved network wait: RF + task 16/16; time + task 7/16',fontsize=12)
fig.text(.01,-.035,'Colors: red = true positive class, blue = true negative class. Only 8 legal test controls; no low-FPR guarantee.',fontsize=9)
for ext in ('png','pdf'):fig.savefig(out/('wait_holdout.'+ext),dpi=180,bbox_inches='tight')
plt.close(fig);files=[out/'wait_all_test_trials.csv',out/'wait_holdout.png',out/'wait_holdout.pdf'];(out/'WAIT_FIGURE_RECEIPT.json').write_text(json.dumps({'source_result_sha256':receipt['sha256'],'files':[{'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]},indent=2));print(json.dumps({'plotted_test_trials':len(rows),'files':[str(p) for p in files]}))
