import argparse, json, pathlib
import numpy as np
from scipy.stats import beta
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
def interval(k,n):
    if not n:return None
    return [0.0 if k==0 else float(beta.ppf(.025,k,n-k+1)),1.0 if k==n else float(beta.ppf(.975,k+1,n-k))]
def score(y,p):
    y=np.array(y,dtype=bool);p=np.array(p,dtype=bool)
    tp=int(np.sum(y&p));fn=int(np.sum(y&~p));fp=int(np.sum(~y&p));tn=int(np.sum(~y&~p))
    return {"tp":tp,"fn":fn,"fp":fp,"tn":tn,"accuracy":float(np.mean(y==p)),"accuracy_95pct":interval(tp+tn,len(y)),"tpr":tp/(tp+fn) if tp+fn else None,"fpr":fp/(fp+tn) if fp+tn else None,"tpr_95pct":interval(tp,tp+fn),"fpr_95pct":interval(fp,fp+tn)}
def model():return make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=2000,random_state=1104))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);a=ap.parse_args();r=pathlib.Path(a.root)
    ledger=json.loads((r/"LEDGER.json").read_text())["records"];matrix=[x for x in ledger if x["stage"]=="matrix"]
    def features(row):
        return np.load(r/"features"/(row["id"]+"_930c.npz"))["features"]
    X=np.array([features(x) for x in matrix]);op=np.array([x["kind"]=="helper" for x in matrix]);y=np.array([x["attack_attempt"] for x in matrix])
    train=np.array([x["block"]<3 for x in matrix]);test=~train
    assert train.sum()==12 and test.sum()==8 and op[train].sum()==6 and op[test].sum()==4
    physical=model().fit(X[train],op[train]);pred_op=physical.predict(X[test])
    rf=model().fit(X[train],y[train]);pred_rf=rf.predict(X[test])
    test_rows=[x for x,t in zip(matrix,test) if t]
    fused=[not x["policy"]["allow_helper" if po else "allow_dns"] for x,po in zip(test_rows,pred_op)]
    result={"scope":"exploratory forward-block holdout; one session; no low-FPR confirmation","n_train":12,"n_test":8,"n_features":X.shape[1],"physical_operation":score(op[test],pred_op),"task_only":score(y[test],[False]*8),"rf_only":score(y[test],pred_rf),"task_plus_rf":score(y[test],fused),"strong_content_audit":score(y[test],[x["strong_software"]["alert"] for x in test_rows]),"predictions":[],"boundary":[]}
    for row,po,pr,pf in zip(test_rows,pred_op,pred_rf,fused):
        result["predictions"].append({"id":row["id"],"block":row["block"],"kind":row["kind"],"policy":row["policy"],"attack":row["attack_attempt"],"predicted_operation":"helper" if po else "dns","rf_only_alert":bool(pr),"fused_alert":bool(pf),"independent_unauthorized_effect":row["unauthorized_effect"]})
    for row in ledger:
        if row["stage"]!="boundary":continue
        f=np.load(r/"features"/(row["id"]+"_930c.npz"))
        diag=row["worker"].get("diagnostics",{});cover=row["worker"].get("cover",{})
        contained=None
        if row["kind"]=="cover_upload":
            contained=cover["begin_ns"]<=diag["upload_begin_ns"]<=diag["upload_end_ns"]<=cover["end_ns"]
        result["boundary"].append({"id":row["id"],"block":row["block"],"kind":row["kind"],"attack":row["attack_attempt"],"upload_inside_cover":contained,"mean_power_db":float(np.average(f["power_db"],weights=f["sample_counts"])),"event_ns":row["worker"]["duration_ns"],"upload_ns":diag.get("upload_end_ns",0)-diag.get("upload_begin_ns",0) if "upload_end_ns" in diag else None,"independent_unauthorized_effect":row["unauthorized_effect"]})
    (r/"EVALUATION.json").write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=="__main__":main()
