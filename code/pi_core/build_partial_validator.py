import ast,hashlib,pathlib
B=pathlib.Path(__file__).resolve().parent;p=B/'validate_confirmations.py'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='d9d9b7d3784bc0fb246e7b783a00816bba84b1678f4891ac67ea1e13c3a3bd03'
s=p.read_text()
changes=[
("for study,n,blocks in [('confirmation_study',80,10),('burst_confirmation_study',72,6)]:","for study,n,blocks in [('confirmation_study',42,6)]:"),
("d=pathlib.Path(json.loads((B/study/'LATEST.json').read_text())['directory']);","d=B/'confirmation_study/confirm_20261105_032747_8137bb';"),
("(d/'COMPLETE.json').exists() and len(rows)==n","(d/'FAILURE.log').exists() and not (d/'COMPLETE.json').exists() and len(rows)==n"),
("post['restore']['rc']==post['rig']['rc']==post['pi_lock_release']==0","post['restore']['rc']==post['pi_lock_release']==0"),
("'CONFIRMATION_COLLECTION_VALIDATION.json'","'CONFIRMATION_PARTIAL_COLLECTION_VALIDATION.json'"),
("'scope':'record and source consistency; not security sample count'","'scope':'42 valid records before a failed 43rd receive; original failure retained; not a completed campaign or pooled primary test'"),
]
for old,new in changes:
 assert s.count(old)==1,old;s=s.replace(old,new)
needle="result={'utc':"
extra="latest=pathlib.Path(json.loads((B/'confirmation_study/LATEST.json').read_text())['directory']);restart=json.loads((latest/'FREEZE.json').read_text());ck('new_preflight_no_prior_workload',latest!=d and restart['rig_preflight']['preflight']['other_workloads']==0 and restart['rig_preflight']['state']=='locked_ready')\n"
assert s.count(needle)==1;s=s.replace(needle,extra+needle)
ast.parse(s);out=B/'validate_confirmation_partial.py';out.write_text(s,encoding='utf-8');print(hashlib.sha256(out.read_bytes()).hexdigest())
