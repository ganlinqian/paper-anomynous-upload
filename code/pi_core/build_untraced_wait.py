"""Create a source-guarded untraced branch; leaves existing studies unchanged."""
import ast,hashlib,pathlib,json
B=pathlib.Path(__file__).resolve().parent
D=B/'untraced_wait_study';D.mkdir(exist_ok=True)
src=B/'wait_confirmation_study/collect_wait_confirm.py'
assert hashlib.sha256(src.read_bytes()).hexdigest()=='b91ebeb6b24b96d07eb34e6b2f0a9e26428d55447185db8c3dd2544cc70a8503'
s=src.read_text()
def once(a,z):
 global s
 assert s.count(a)==1,(a,s.count(a));s=s.replace(a,z)
once("campaign='waitconfirm_'","campaign='untracedwait_'")
s=s.replace("<DATA>/telltale_wait_confirmation_20261105","F:/Data/telltale_untraced_wait_20261105")
once("B.parent/'burst_confirmation_study/LATEST.json'","B.parent/'wait_confirmation_study/LATEST.json'")
anchor="  assert sha(B.parent/'analysis_extensions/WAIT_CONFIRMATION_MODELS.json')"
assert s.count(anchor)==1
s=s.replace(anchor,"  process=B.parent/'confirmation_processing_20261105';assert (process/'F_UPLOAD_COMPLETE.json').exists();assert (process/'J/HASH_COMPLETE.json').exists();assert not (process/'FAILURE.log').exists()\n"+anchor)
once("cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 strace -f -qq -ttt -T -yy -s 4096 -e trace=execve,openat,network -o '+stem+'.strace python3 -u '+pr+'/pi_api.py --private-config '+stem+'.json'","cmd='env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 python3 -u '+pr+'/pi_api.py --private-config '+stem+'.json'")
once("assert ready['ready'] and ready['input_sha256']==input_sha;return stem,td,ready","assert ready['ready'] and ready['input_sha256']==input_sha;status=run(p,'cat /proc/'+str(pid)+'/status')['stdout'];tracer=int(next(x.split()[1] for x in status.splitlines() if x.startswith('TracerPid:')));assert tracer==0;ready['independently_checked_tracer_pid']=tracer;return stem,td,ready")
lines=s.splitlines()
matched=[i for i,t in enumerate(lines) if t.startswith("   pf.get(stem+'.private.json'")]
assert len(matched)==1
lines[matched[0]]="   pf.get(stem+'.private.json',str(td/'worker.private.json'));private=json.loads((td/'worker.private.json').read_text());return private,None"
s="\n".join(lines)+"\n"
once("for active,cover in [(a,c) for a in (False,True) for c in (False,True)]","for active,cover in [(a,c) for a in (False,True) for c in (False,)]")
once("and gzip_exec==active","and gzip_exec is None and bool(private['archive_inside_wait'])==active")
once("for cover in (False,True)","for cover in (False,)")
once("random.Random(2026110510+block)","random.Random(2026110513+block)")
once("cfg.update(id='g'","cfg.update(id='u'")
once("stage='wait_confirmation'","stage='untraced_wait_confirmation'")
once("'stage':'wait_confirmation'","'stage':'untraced_wait_confirmation'")
once("B/'collect_wait_confirm.py'","B/'collect_untraced_wait.py'")
once("B.parent/'analysis_extensions/WAIT_MODELS_RECEIPT.json']","B.parent/'analysis_extensions/WAIT_MODELS_RECEIPT.json',B.parent/'analysis_extensions/RELATIVE_REFERENCE_MODELS.json',B.parent/'analysis_extensions/EXECUTION_WINDOW_MODELS.json']")
once("'trusted_policy_in_worker':False,","'trusted_policy_in_worker':False,'syscall_tracing':False,'all_trials_test_only':True,")
once("kernel_gzip_exec=gzip_exec","kernel_exec_audit_measured=False")
once("and gzip_exec==cfg['actual_active'] and","and gzip_exec is None and")
once("row['rf']=rig.rpc({'op':'finish'});private,gzip_exec=","row['rf']=rig.rpc({'op':'finish'});row['rf_finish_desktop_ns']=time.perf_counter_ns();row['flush_sent_desktop_ns']=time.perf_counter_ns();private,gzip_exec=")
once("valid=valid and (not cfg['actual_active'] or private['archive_inside_wait'])","valid=valid and bool(private['archive_inside_wait'])==cfg['actual_active'] and row['flush_sent_desktop_ns']>row['rf_finish_desktop_ns']")
once("rig=Rig(w,rs,wr,campaign);plan=[]","rig=Rig(w,rs,wr,campaign);assert int(rig.pre['preflight']['free'])>=32480000000;plan=[]")
# The preflight schema is checked separately before scheduling.
ast.parse(s);assert ' strace -f ' not in s and "host.strace" not in s
out=D/'collect_untraced_wait.py';assert not out.exists();out.write_text(s,encoding='utf-8')
worker=B/'wait_confirmation_study/pi_api.py';assert hashlib.sha256(worker.read_bytes()).hexdigest()=='4b1205548742d2922cb5b6fa9651ca74f597ff8e695c65fe8845dfeba0ce989f'
assert not (D/'pi_api.py').exists();(D/'pi_api.py').write_bytes(worker.read_bytes())
v=B/'validate_wait_confirmation.py';assert hashlib.sha256(v.read_bytes()).hexdigest()=='c600585d79ca40ddadb1e14739dbaa68ec47aa4aaa744270e568ba6cfc3cff14'
s=v.read_text()
once("b/'wait_confirmation_study/LATEST.json'","b/'untraced_wait_study/LATEST.json'")
once("check('trials64',len(rows)==64 and len({x['id'] for x in rows})==64)","check('trials32',len(rows)==32 and len({x['id'] for x in rows})==32)")
lines=s.splitlines();matched=[i for i,t in enumerate(lines) if t.startswith("  ident=row['id']")]
assert len(matched)==1
lines[matched[0]]="  ident=row['id'];td=d/'records'/ident;private=json.loads((td/'worker.private.json').read_text());cfg=json.loads((td/'private_config.json').read_text());trace=json.loads((td/'canonical_trace.json').read_text());exec_seen=None;ev=[e for e in events if row['dispatch_desktop_ns']<=e['begin_desktop_ns']<=e['end_desktop_ns']<=row['return_desktop_ns'] and e['token']==row['request']['id']];check(ident+':single_gateway',len(ev)==1)"
s="\n".join(lines)+"\n"
once("check(ident+':independent_exec',exec_seen==row['actual_active']==row['kernel_gzip_exec'])","check(ident+':tracing_disabled',row['kernel_exec_audit_measured'] is False and row['ready']['independently_checked_tracer_pid']==0 and not (td/'host.strace').exists());check(ident+':flush_after_RF',row['flush_sent_desktop_ns']>row['rf_finish_desktop_ns'])")
s=s.replace('WAIT_CONFIRMATION_COLLECTION_VALIDATION','UNTRACED_WAIT_COLLECTION_VALIDATION').replace('WAIT_CONFIRMATION_TIMING_TRIALS','UNTRACED_WAIT_TIMING_TRIALS')
once(" for block in range(8):check('same_api:'"," check('no_syscall_tracing',freeze['syscall_tracing'] is False);check('archives16',archive_count==16);check('no_SHA_cover',all(x['cover'] is False for x in rows))\n plan={x['id']:x for x in freeze['plan']}\n for x in rows:check(x['id']+':planned',all(x[k]==plan[x['id']][k] for k in ('id','block','actual_active','expected_active','cover','request','attack_attempt')))\n for block in range(8):\n  group=[x for x in rows if x['block']==block];check('balanced_cells:'+str(block),len(group)==4 and {(x['actual_active'],x['expected_active']) for x in group}=={(a,e) for a in (False,True) for e in (False,True)})\n for block in range(8):check('same_api:'")
ast.parse(s);out=B/'validate_untraced_wait.py';assert not out.exists();out.write_text(s,encoding='utf-8')
print(json.dumps({'collector_sha256':hashlib.sha256((D/'collect_untraced_wait.py').read_bytes()).hexdigest(),'worker_sha256':hashlib.sha256((D/'pi_api.py').read_bytes()).hexdigest(),'validator_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'trials':32,'new_training':False}))
