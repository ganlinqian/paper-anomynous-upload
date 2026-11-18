import hashlib,pathlib
b=pathlib.Path(__file__).resolve().parent;s=b.parent/'complete_trace_study/collect_trace.py';data=s.read_bytes();assert hashlib.sha256(data).hexdigest()=='0210c3871aecf79804f8a85c917e51247bea400c415b7653ee7db5b2d42f4406';text=data.decode();text=text.replace("campaign='trace_'","campaign='order_'").replace('telltale_complete_trace_20261104','telltale_order_20261104').replace("'burst.c'","'ordered.c'").replace("B.parent/'burst_study/ordered.c'","B/'ordered.c'").replace("/burst.c","/ordered.c").replace('/libburst.so','/libordered.so').replace("'collect_trace.py'","'collect_order.py'").replace("'expected_active'","'expected_order'").replace("'actual_active'","'actual_order'").replace("'stage':'trace'","'stage':'order'").replace("stage='trace'","stage='order'").replace('2026110406','2026110405').replace("'duration_code':'1000' if cfg['actual_order'] else '0000'","'order_code':'M_C_' if cfg['actual_order'] else 'C_M_'").replace("((row['private']['operations']>0)==cfg['actual_order'])","([q['kind'] for q in row['private']['phases']]==(['memory','cpu'] if cfg['actual_order'] else ['cpu','memory']))")
text=text.replace("B.parent/'burst_study/ordered.c'","B/'ordered.c'")
assert "'duration_code'" not in text;assert "row['private']['operations']" not in text
path=b/'collect_order.py'
if path.exists():assert path.read_text()==text
else:path.write_text(text)
print(hashlib.sha256(path.read_bytes()).hexdigest())
