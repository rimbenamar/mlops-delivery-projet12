import hashlib
import json
import os
from pathlib import Path
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, average_precision_score, balanced_accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from mlflow.models import infer_signature
from app.domain import FEATURES, NAME
from app.model import ThresholdClassifier

DATA=Path(__file__).resolve().parents[1]/"data"

def load_data():
    meta=json.loads((DATA/"metadata.json").read_text())
    path=DATA/"deliveries.csv"
    if hashlib.sha256(path.read_bytes()).hexdigest()!=meta["sha256"]:
        raise ValueError("Dataset checksum mismatch. Regenerate metadata with scripts/prepare_data.py.")
    df=pd.read_csv(path,parse_dates=["purchase_date"])
    if df[FEATURES+["late"]].isna().any().any() or set(df.late.unique())!={0,1}: raise ValueError("Invalid dataset")
    return df.sort_values("purchase_date",kind="stable"),meta

def split_data(df):
    # Whole dates, preventing the same calendar day appearing across splits.
    dates=np.sort(df.purchase_date.dt.normalize().unique())
    cut1=dates[int(len(dates)*.70)];cut2=dates[int(len(dates)*.85)]
    day=df.purchase_date.dt.normalize()
    return df[day<cut1],df[(day>=cut1)&(day<cut2)],df[day>=cut2]

def train():
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI","http://localhost:5000"))
    mlflow.set_experiment("projet12-delivery-olist")
    df,meta=load_data();training,validation,test=split_data(df)
    X=training[FEATURES].to_numpy(dtype=float);y=training.late.to_numpy()
    with mlflow.start_run() as run:
        params=dict(n_estimators=160,max_depth=12,min_samples_leaf=12,class_weight="balanced_subsample",random_state=42,n_jobs=1)
        model=RandomForestClassifier(**params).fit(X,y)
        val_prob=model.predict_proba(validation[FEATURES].to_numpy(dtype=float))[:,1]
        thresholds=np.linspace(.1,.8,71)
        threshold=float(max(thresholds,key=lambda t:f1_score(validation.late,val_prob>=t,zero_division=0)))
        test_X=test[FEATURES].to_numpy(dtype=float);prob=model.predict_proba(test_X)[:,1];pred=(prob>=threshold).astype(int)
        metrics={"accuracy":accuracy_score(test.late,pred),"balanced_accuracy":balanced_accuracy_score(test.late,pred),"precision_late":precision_score(test.late,pred,zero_division=0),"recall_late":recall_score(test.late,pred,zero_division=0),"f1_late":f1_score(test.late,pred,zero_division=0),"roc_auc":roc_auc_score(test.late,prob),"average_precision":average_precision_score(test.late,prob),"baseline_accuracy":float((test.late==0).mean()),"late_rate_test":float(test.late.mean())}
        mlflow.log_params({**params,"decision_threshold":threshold,"split":"chronological_70_15_15_calendar_dates","rows_train":len(training),"rows_validation":len(validation),"rows_test":len(test),"dataset_sha256":meta["sha256"]})
        mlflow.log_metrics(metrics)
        mlflow.set_tags({"dataset":"Olist real historical orders","purpose":"academic","target":"delivered_calendar_day_after_promised_day"})
        model=ThresholdClassifier(model,threshold)
        mlflow.sklearn.log_model(model,"model",code_paths=[str(Path(__file__).parent)],signature=infer_signature(X,model.predict(X)),input_example=X[:2])
        samples=training.sample(n=min(300,len(training)),random_state=42)[FEATURES].to_numpy(dtype=float)
        examples=[]
        for index in [int(np.argmin(prob)),int(np.argmin(np.abs(prob-threshold))),int(np.argmax(prob))]:
            examples.append({"input":dict(zip(FEATURES,test_X[index].tolist())),"actual_late":int(test.late.iloc[index]),"predicted_risk":float(prob[index])})
        periods={name:{"rows":len(part),"start":str(part.purchase_date.min()),"end":str(part.purchase_date.max()),"late_rate":float(part.late.mean())} for name,part in [("train",training),("validation",validation),("test",test)]}
        reference={"features":FEATURES,"classes":["on_time","late"],"threshold":threshold,"mean":X.mean(axis=0).tolist(),"std":X.std(axis=0).tolist(),"samples":samples.tolist(),"examples":examples,"dataset":meta,"splits":periods,"confusion_matrix":confusion_matrix(test.late,pred).tolist(),"feature_importance":dict(zip(FEATURES,model.feature_importances_.tolist()))}
        mlflow.log_dict(reference,"reference.json");mlflow.log_dict(meta,"dataset_metadata.json")
        client=mlflow.MlflowClient();version=mlflow.register_model(f"runs:/{run.info.run_id}/model",NAME)
        client.set_registered_model_alias(NAME,"champion",version.version)
        report={"run_id":run.info.run_id,"version":version.version,"threshold":threshold,"metrics":metrics,"splits":periods}
        print(json.dumps(report,indent=2));return report

if __name__=="__main__": train()
