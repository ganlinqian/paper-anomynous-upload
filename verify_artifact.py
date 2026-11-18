#!/usr/bin/env python3
"""Fast, read-only integrity and paper-endpoint checks; no fitting, network, or capture."""
from pathlib import Path, PurePosixPath
import csv,hashlib,json,re
if not __debug__:
 raise SystemExit('Verification requires assertions: run without -O/-OO and unset PYTHONOPTIMIZE.')
ROOT=Path(__file__).resolve().parent

def main():
 manifest=ROOT/'ARTIFACT_MANIFEST.json'
 assert manifest.is_file(), 'ARTIFACT_MANIFEST.json is missing'
 entries=json.loads(manifest.read_text())
 for row in entries:
  f=ROOT/row['path'];assert f.is_file(),row['path']
  assert f.stat().st_size==row['bytes'] and hashlib.sha256(f.read_bytes()).hexdigest()==row['sha256'],row['path']
 print('SHA-256 verified:',len(entries),'distributed files')
 for row in json.loads((ROOT/'ORIGINAL_HASHES.json').read_text()):
  assert set(row)=={'path','original_sha256','artifact_sha256'}
  p=PurePosixPath(row['path']);assert not p.is_absolute() and '..' not in p.parts and ':' not in row['path'] and '\\' not in row['path']
  assert all(re.fullmatch('[0-9a-f]{64}',row[k]) for k in ('original_sha256','artifact_sha256'))
 print('Source digest map contains only relative paths and SHA-256 values')
 C=ROOT/'data/pi_adaptive_desktop/experiments/campaigns'
 expected={'s1e':64,'s1f':64,'s1g':80,'s1i':80,'s1j':88,'s1k':88,'s1l':87,'s1p':88}
 for stage,n in expected.items():
  info=json.loads((C/('LATEST_'+stage+'.json')).read_text());d=C/info['campaign'];rows=json.loads((d/'RESULTS.json').read_text());test=[x for x in rows if x['condition']!='silent_cal'];assert len(test)==n,(stage,len(test),n)
 print('C30--C36 and C38 test denominators verified')
 n37=0
 for stage in ['s1m','s1n']:
  d=C/json.loads((C/('LATEST_'+stage+'.json')).read_text())['campaign'];n37+=sum(x['condition']!='silent_cal' for x in json.loads((d/'RESULTS.json').read_text()))
 assert n37==115,n37
 d=C/json.loads((C/'LATEST_s1p.json').read_text())['campaign'];records={x['id']:x for x in json.loads((d/'RESULTS.json').read_text())};p35={x['id']:x['alert']=='True' for x in csv.DictReader((d/'predictions_c35.csv').open()) if x['detector']=='C35/self_roll4_p70'};p38={x['id']:x['alert_p50']=='True' for x in csv.DictReader((d/'predictions_c38.csv').open()) if x['detector']=='C38/roll4'}
 def count(conditions):
  ids=[i for i,r in records.items() if r['condition'] in conditions];return [sum(p35[i] or p38[i] for i in ids),len(ids)]
 assert count(['persist09','persist12','persist12s','persist25'])==[31,32]
 assert count(['silent','bg_log'])==[2,32]
 assert count(['gzip16','gzip3_d19','sha32'])==[24,24]
 print('C37 test n=115; C38 frozen composite: 31/32 sustained, 2/32 false alarms, 24/24 ordinary hidden')
 power=json.loads((ROOT/'data/power_c36/c36d_power_baseline.json').read_text());assert power['hidden']==[21,48] and power['negFA']==[3,39]
 r1=json.loads((ROOT/'data/r1/r1-rules-v2/r1_coverage.json').read_text());d=r1['datasets'];assert d['swe-agent sample']['tool_calls']==5613 and d['openhands sample']['tool_calls']==3459
 print('C36 power and R1 saved endpoints verified')
 for row in json.loads((ROOT/'assets/chunks.json').read_text()):
  h=hashlib.sha256();n=0
  for part in row['parts']:
   raw=(ROOT/part['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==part['sha256'];h.update(raw);n+=len(raw)
  assert h.hexdigest()==row['sha256'] and n==row['bytes'],row['path']
 print('Large-recording chunks and reconstructed hashes verified')
 print('ALL CHECKS PASSED')
if __name__=='__main__':main()
