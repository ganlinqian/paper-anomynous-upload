"""Small result-only paired block summaries; never fits or selects a detector."""
import argparse,hashlib,itertools,json,math,pathlib
def compare(left,right,observations):
    a={x['id']:x for x in left};b={x['id']:x for x in right}
    assert a.keys()==b.keys()
    groups={}
    for ident in a:
        x,y,o=a[ident],b[ident],observations[ident]
        truth=bool(o.get('attack',o.get('violation',bool(o['actual_active'])!=bool(o['expected_active']))))
        ca=bool(x['alert'])==truth;cb=bool(y['alert'])==truth
        groups.setdefault(o['block'],[]).append((int(ca),int(cb)))
    blocks=[]
    for block,pairs in sorted(groups.items()):
        blocks.append({'block':block,'n':len(pairs),'left_correct':sum(x for x,y in pairs),'right_correct':sum(y for x,y in pairs),'accuracy_difference':sum(x-y for x,y in pairs)/len(pairs)})
    diffs=[x['accuracy_difference'] for x in blocks];nz=[x for x in diffs if x!=0]
    assert len(nz)<=20
    observed=abs(sum(diffs))
    perm=[abs(sum(s*d for s,d in zip(signs,nz))) for signs in itertools.product((-1,1),repeat=len(nz))]
    return {'n_trials':len(a),'n_blocks':len(blocks),'blocks':blocks,'mean_block_accuracy_difference':sum(diffs)/len(diffs),'two_sided_block_sign_flip_p':sum(z>=observed-1e-12 for z in perm)/len(perm),'assumption':'Descriptive sensitivity analysis assuming independent blocks and exchangeable signs of paired block differences under a symmetric null; not proof of deployment generalization or a randomized causal test. Models are unchanged. Small block counts limit resolution.'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    p=pathlib.Path(a.input);d=json.loads(p.read_text());obs={x['id']:x for x in d['all_trial_observations']}
    left=d['models']['whole_260']['predictions'];kernel=[{'id':x['id'],'alert':bool(x['kernel_exec_seen'])!=bool(x['expected_active'])} for x in d['all_trial_observations'] if x['id'] in {z['id'] for z in left}]
    out={'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'scope':'post hoc uncertainty audit of original C07; not newly prespecified evidence','comparisons':{k:compare(left,z['predictions'],obs) for k,z in d['timing'].items()}}
    out['comparisons']['trusted_kernel']=compare(left,kernel,obs)
    pathlib.Path(a.output).write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps({k:{x:v[x] for x in ('n_blocks','mean_block_accuracy_difference','two_sided_block_sign_flip_p')} for k,v in out['comparisons'].items()}))
if __name__=='__main__':main()
