import ast,hashlib,pathlib
B=pathlib.Path(__file__).resolve().parent;p=B/'validate_confirmations.py'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='d9d9b7d3784bc0fb246e7b783a00816bba84b1678f4891ac67ea1e13c3a3bd03'
s=p.read_text()
for old,new in [("for study,n,blocks in [('confirmation_study',80,10),('burst_confirmation_study',72,6)]:","for study,n,blocks in [('confirmation_study',80,10)]:"),("'CONFIRMATION_COLLECTION_VALIDATION.json'","'C08_COLLECTION_VALIDATION.json'")]:
 assert s.count(old)==1;s=s.replace(old,new)
ast.parse(s);out=B/'validate_c08_only.py';out.write_text(s,encoding='utf-8');print(hashlib.sha256(out.read_bytes()).hexdigest())
