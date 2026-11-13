import numpy as np
from sklearn.ensemble import RandomForestClassifier
from app.model import ThresholdClassifier
from app.train import load_data, split_data
from app.domain import FEATURES

def test_chronological_split_and_no_target_leakage():
    df,metadata=load_data();train,val,test=split_data(df)
    assert len(df)==metadata['rows']
    assert train.purchase_date.max()<val.purchase_date.min()<test.purchase_date.min()
    assert val.purchase_date.max()<test.purchase_date.min()
    assert len(train)+len(val)+len(test)==len(df)
    assert 'late' not in FEATURES
    assert not any('delivered' in name for name in FEATURES)
    for part in [train,val,test]:assert set(part.late.unique())=={0,1}

def test_registered_estimator_respects_threshold():
    X=np.array([[0.],[1.],[2.],[3.]])
    forest=RandomForestClassifier(n_estimators=10,random_state=42).fit(X,[0,0,1,1])
    model=ThresholdClassifier(forest,.3)
    assert np.array_equal(model.predict(X),(model.predict_proba(X)[:,1]>=.3).astype(int))
