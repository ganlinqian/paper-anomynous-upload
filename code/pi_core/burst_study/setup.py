import hashlib,pathlib
b=pathlib.Path(__file__).resolve().parent;p=b.parent
for name,expected in [('bridge_utils.py','7017efab335b82d5161047c2229dde7080504e9a58a4cc1ec91df4e06b13b243'),('rig_capture.py','29a4ece9f939786a91ee311cfc8327b782f5a74277a659a48eaa07e94a8b481d')]:
 data=(p/name).read_bytes();assert hashlib.sha256(data).hexdigest()==expected,name
 if name=='rig_capture.py':
  s=data.decode();s=s.replace('root=pathlib.Path(a.root);root.mkdir(parents=True,exist_ok=False)','root=pathlib.Path(a.root);drive=root.drive.rstrip(\":\");assert drive in (\"F\",\"J\"),\"only verified SATA drives\";root.mkdir(parents=True,exist_ok=False)')
  s=s.replace("DeviceID='J:'","DeviceID='\"+drive+\":'").replace("new('J')","new('\"+drive+\"')").replace('unknown J mapping','unknown target mapping').replace('unsafe J bus','unsafe target bus')
  s=s.replace('pre[\"query_user\"]=', 'pre[\"target_drive\"]=drive;pre[\"concurrent_source_transfer\"]=True\n        pre[\"query_user\"]=')
  data=s.encode()
 target=b/name
 if target.exists():assert target.read_bytes()==data,name
 else:target.write_bytes(data)
 print(name,hashlib.sha256(data).hexdigest())
