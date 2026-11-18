#!/usr/bin/env python3
"""Rebuild large numeric recordings from anonymous-host-compatible chunks; verify every SHA-256."""
from pathlib import Path
import hashlib,json,os
ROOT=Path(__file__).resolve().parents[1]
def main():
 entries=json.loads((ROOT/'assets/chunks.json').read_text())
 for row in entries:
  target=ROOT/row['path'];target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256']:
   print('verified',row['path']);continue
  tmp=target.with_name(target.name+'.assembling');digest=hashlib.sha256();size=0
  try:
   with tmp.open('wb') as out:
    for part in row['parts']:
     raw=(ROOT/part['path']).read_bytes()
     if hashlib.sha256(raw).hexdigest()!=part['sha256']:raise ValueError('Damaged chunk: '+part['path'])
     out.write(raw);digest.update(raw);size+=len(raw)
   if size!=row['bytes'] or digest.hexdigest()!=row['sha256']:raise ValueError('Recording checksum mismatch: '+row['path'])
   os.replace(tmp,target);print('rebuilt',row['path'])
  finally:
   if tmp.exists():tmp.unlink()
if __name__=='__main__':main()
