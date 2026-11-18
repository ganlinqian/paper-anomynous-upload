from pathlib import Path
import hashlib,json
B=Path(__file__).resolve().parent;p=B/'resume_boundary_processing_20261105_0755.py';assert hashlib.sha256(p.read_bytes()).hexdigest()=='c845e2832d3b75a7bb1f6d3e5385756a04687c5fafce01dcecad402e1e9bbdbf'
s=p.read_text(encoding='utf-8-sig')
anchor="Base=UntracedPipe if a.dataset=='C13' else SustainedPipe\n"
insert="""import socket
endpoint=json.loads((B/'untraced_processing_20261105/VERIFIED_ENDPOINT_20261105_0806.json').read_text(encoding='utf-8-sig'))
assert endpoint['strict_original_hostname_hostkey_verified'] and endpoint['connect_ip']=='198.51.100.1'
_original_getaddrinfo=socket.getaddrinfo
def _session_endpoint_resolver(host,port,*args,**kwargs):
 return _original_getaddrinfo(endpoint['connect_ip'] if host==endpoint['hostname'] else host,port,*args,**kwargs)
socket.getaddrinfo=_session_endpoint_resolver
def configure_native(p):
 raw=(p.out/'ssh_config').read_text(encoding='utf-8-sig')
 old=' HostName '+endpoint['hostname']+'\\n'
 assert raw.count(old)==1 and p.cfg['host']==endpoint['hostname']
 alias=' HostKeyAlias ['+endpoint['hostname']+']:'+str(p.cfg['port'])+'\\n'
 text=raw.replace(old,' HostName '+endpoint['connect_ip']+'\\n'+alias,1)
 (p.out/'ssh_config.endpoint_0806').write_text(text,encoding='utf-8',newline='')
 save(p.out/'SESSION_ENDPOINT_BINDING.json',{'utc':stamp(),'ip':endpoint['connect_ip'],'hostname_for_hostkey_check':endpoint['hostname'],'port':p.cfg['port'],'strict_check':True,'endpoint_receipt_sha256':sha(B/'untraced_processing_20261105/VERIFIED_ENDPOINT_20261105_0806.json'),'system_DNS_changed':False})
"""
assert s.count(anchor)==1;s=s.replace(anchor,anchor+insert,1)
for old,new in [
("'f870e2a66ad441e13df4f5b503d2c077c8ef58ac669190425d92c5aa7102ab95'","'0cf9c0d02badb0e170ca6c9dcf0d567be2cd12bdc67e26315b62dbd1851977b3'"),
("'85ad54442e0bb4a51ba3b7be57ea4113e530f50ade0340a30e4db6d09ab1344b'","'3d707ddee08a6c31b6c11b849bdb7aa9fb3251178c5057ee4b4231099fe8404e'"),
("network_drop_20261105_0745","network_drop_20261105_0802"),
("failure_20261105_0745","failure_20261105_0802"),
("'own C13 controller failed; preserve artifacts'","'own recovery failed; preserve artifacts'"),
("'recovery_'+row['filename']","'endpoint_recovery_'+row['filename']"),
("str(self.out/'ssh_config')","str(self.out/'ssh_config.endpoint_0806')"),
("target+'.recovery_'","target+'.endpoint_recovery_'"),
(" p.transfer(files,'F');"," configure_native(p)\n p.transfer(files,'F');")
]:
 assert old in s,old;s=s.replace(old,new)
q=B/'resume_boundary_processing_20261105_0806.py';assert not q.exists();q.write_text(s,encoding='utf-8',newline='')
print(json.dumps({'path':str(q),'sha256':hashlib.sha256(q.read_bytes()).hexdigest(),'bytes':q.stat().st_size}))
