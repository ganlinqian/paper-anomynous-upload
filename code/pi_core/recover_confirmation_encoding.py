"""Preserve failed controllers and reuse completed source hashes after UTF-8 repair."""
import ast,datetime,hashlib,json,pathlib,shutil
B=pathlib.Path(__file__).resolve().parent
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
D=B/'confirmation_processing_20261105'
assert (D/'FAILURE.log').exists() and 'UnicodeDecodeError' in (D/'FAILURE.log').read_text(encoding='utf-8-sig')
assert not (D/'BRIDGE_PICK.json').exists() and not (D/'REMOTE_CONFIG.json').exists()
F=D/'F'
expected={'HASH_COMMAND.json':'21fe750d17db78104d3ed73625672e658db2e1162c06aa2163ffcee6f33463d3','HASH_COMPLETE.json':'6d653a2fbffeaabf50b695aad996be8f897a05df59525374ae2ae7d50d347916','SOURCE_RECEIPTS.json':'02df2e126e627a4952cff84ac2393024cf47502f1cba387475487dbb97812404','MANIFEST.json':'b38ab67d1e758879986186601ca653010afb2173e363073471460b63570ef0a4'}
for n,h in expected.items():assert sha(F/n)==h,n
assert json.loads((F/'HASH_COMMAND.json').read_text(encoding='utf-8-sig'))['rc']==0
assert json.loads((F/'HASH_COMPLETE.json').read_text(encoding='utf-8-sig'))['files']==244
for n in ['process_confirmations.py','confirmation_pipeline_utils.py','watch_early_confirmations.py','untraced_wait_study/after_main_J_hash.py']:ast.parse((B/n).read_text(encoding='utf-8'))
# Reconstruct and hash-check the exact pre-repair main source for the audit archive.
now=(B/'process_confirmations.py').read_text(encoding='utf-8')
before=now.replace("json.loads(q.read_text(encoding='utf-8-sig'))['returncode']==0","json.loads(q.read_text())['returncode']==0",1).replace("\n p.state('failed',detail='see preserved FAILURE.log')","")
candidates=[before.encode(),before.replace('\n','\r\n').encode()]
original_bytes=next((v for v in candidates if hashlib.sha256(v).hexdigest()=='6e950261324f56b3786c59d7fe6e4334b119b3558f49dac59d2873600b3b032e'),None)
assert original_bytes is not None,'pre-repair source must match exact original raw-byte SHA'
archive=B/('confirmation_processing_failed_encoding_'+stamp);assert not archive.exists();D.rename(archive)
(archive/'process_confirmations_before.py').write_bytes(original_bytes)
(archive/'RECOVERY_SOURCE_SHA.json').write_text(json.dumps({'before_main':'6e950261324f56b3786c59d7fe6e4334b119b3558f49dac59d2873600b3b032e','after_main':sha(B/'process_confirmations.py'),'before_utils':'bcda800c3fc0fd2d87433ccadf13d25ee23ccd8264bbe5ab29c0dce76889a62b','after_utils':sha(B/'confirmation_pipeline_utils.py'),'cause':'Windows GBK default decoding a UTF-8 resource-release receipt after completed source hashing','no_remote_allocation_before_failure':True},indent=2),encoding='utf-8')
early=B/'analysis_extensions/early_confirm_20261105'
assert (early/'FAILURE.log').exists() and not list(early.glob('EARLY_CONFIRMATION*.json'))
early_archive=early.with_name('early_confirm_failed_encoding_'+stamp);early.rename(early_archive)
queue=B/'untraced_wait_study';qa=queue/('queue_failed_upstream_'+stamp);qa.mkdir()
for n in ['QUEUE_STATUS.json','QUEUE_FAILURE.log']:
 if (queue/n).exists():(queue/n).rename(qa/n)
for prefix,dest in [('process-confirmations',archive),('early-confirmations',early_archive),('untraced-wait',qa)]:
 target=dest/'job_logs';target.mkdir()
 for q in (B/'jobs').glob(prefix+'.*'):q.rename(target/q.name)
request={'source_dir':str(archive/'F'),'artifact_sha256':expected,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'reuse completed hashes plus current-size checks; never claim fresh raw rehash'}
(B/'F_HASH_REUSE_REQUEST_20261105_0452.json').write_text(json.dumps(request,indent=2),encoding='utf-8')
print(json.dumps({'main_archive':str(archive),'early_archive':str(early_archive),'queue_archive':str(qa),'cached_hash_files':244,'source_bytes':39040000000,'raw_rehashed_now':False}))
