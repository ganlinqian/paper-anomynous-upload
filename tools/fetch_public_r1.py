#!/usr/bin/env python3
"""Fetch the exact public R1 inputs from pinned upstream revisions, verifying original SHA-256."""
from pathlib import Path
import hashlib,json,os,urllib.request
ROOT=Path(__file__).resolve().parents[1]
def main():
 out=ROOT/'external/r1';out.mkdir(parents=True,exist_ok=True)
 for row in json.loads((ROOT/'data/r1/public_sources.json').read_text()):
  target=out/row['local_filename']
  if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256']:
   print('verified',target.name);continue
  tmp=target.with_name(target.name+'.downloading');digest=hashlib.sha256();size=0
  try:
   req=urllib.request.Request(row['url'],headers={'User-Agent':'telltale-artifact-reproduction'})
   with urllib.request.urlopen(req,timeout=90) as response,tmp.open('wb') as f:
    while True:
     block=response.read(1024*1024)
     if not block:break
     f.write(block);digest.update(block);size+=len(block)
   if size!=row['bytes'] or digest.hexdigest()!=row['sha256']:raise ValueError('Upstream input changed or download damaged: '+row['dataset'])
   os.replace(tmp,target);print('downloaded and verified',target.name)
  finally:
   if tmp.exists():tmp.unlink()
if __name__=='__main__':main()
