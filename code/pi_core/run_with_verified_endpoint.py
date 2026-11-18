"""Scoped resolver for a recently resolved endpoint, retaining original hostname SSH key checks."""
from pathlib import Path
import json,runpy,socket,sys
B=Path(__file__).resolve().parent
j=json.loads((B/'untraced_processing_20261105/VERIFIED_ENDPOINT_20261105_0806.json').read_text(encoding='utf-8-sig'))
assert j['strict_original_hostname_hostkey_verified'] and j['hostname']=='dev.cloud' and j['connect_ip']=='198.51.100.1'
original=socket.getaddrinfo
def scoped(host,port,*a,**kw):return original(j['connect_ip'] if host==j['hostname'] else host,port,*a,**kw)
socket.getaddrinfo=scoped
script=Path(sys.argv[1]);sys.argv=sys.argv[1:];runpy.run_path(str(script),run_name='__main__')
