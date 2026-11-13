import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app import main
from app.domain import FEATURES

VALID=dict(distance_km=350.,weight_kg=1.2,price_brl=150.,freight_brl=25.,promised_days=15,item_count=1,purchase_weekday=0,purchase_month=5)

@pytest.fixture()
def client():
    class Fake:
        classes_=np.array([0,1])
        def predict_proba(self,X):return np.array([[.65,.35]])
    main.state.clear()
    main.state.update(model=Fake(),version='test',reference={
        'features':FEATURES,'classes':['on_time','late'],'threshold':.3,
        'mean':list(VALID.values()),'std':[1.]*8,'samples':[list(VALID.values())],
        'examples':[],'dataset':{},'splits':{},'feature_importance':{}})
    main.window.clear();main.history.clear();main.drift_flag.set(0)
    yield TestClient(main.app,raise_server_exceptions=False)

def test_threshold_prediction(client):
    r=client.post('/predict',json=VALID);assert r.status_code==200
    d=r.json();assert d['class_id']==1;assert d['class_name']=='late'
    assert d['delay_probability']==.35;assert sum(d['probabilities'])==pytest.approx(1)
    assert d['decision_threshold']==.3

@pytest.mark.parametrize('data',[{},dict(VALID,extra=1),dict(VALID,distance_km='350'),dict(VALID,weight_kg=-1.),dict(VALID,promised_days=3.5),dict(VALID,purchase_weekday=7),dict(VALID,purchase_month=13),dict(VALID,item_count=0)])
def test_schema(client,data):assert client.post('/predict',json=data).status_code==422

def test_drift_and_recovery(client):
    shifted=dict(VALID,distance_km=5000.,weight_kg=50.)
    for _ in range(35):assert client.post('/predict',json=shifted).status_code==200
    assert main.drift_flag._value.get()==1
    for _ in range(200):client.post('/predict',json=VALID)
    assert main.drift_flag._value.get()==0
    assert len(main.window)==200;assert len(main.history)==12
    text=client.get('/metrics').text
    assert 'prediction_latency_seconds_bucket' in text
    assert 'http_requests_total' in text

def test_error_instrumentation(client,monkeypatch):
    def fail(row):raise RuntimeError('test')
    monkeypatch.setattr(main,'infer',fail)
    assert client.post('/predict',json=VALID).status_code==500
    assert 'status="500"' in client.get('/metrics').text

def test_static_and_examples(client):
    assert 'DeliveryOps' in client.get('/').text
    assert client.get('/static/app.js').status_code==200
    assert client.get('/static/style.css').status_code==200
    assert client.get('/model').json()['name']=='delivery-delay-classifier'
    assert client.get('/dashboard/traffic-sample').json()['features']==FEATURES

def test_overview_outage(client,monkeypatch):
    class Offline:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,*args,**kwargs):raise httpx.ConnectError('offline')
    monkeypatch.setattr(main.httpx,'AsyncClient',lambda **kw:Offline())
    client.post('/predict',json=VALID)
    r=client.get('/dashboard/overview');assert r.status_code==200
    d=r.json();assert d['services']['api'];assert not d['services']['prometheus']
    assert d['metrics']['p95'] is None;assert d['drift']['detected'] is None
    assert len(d['recent'])==1

def test_overview_nan(client,monkeypatch):
    class Online:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,url,**kwargs):
            body={'data':{'result':[{'value':[0,'NaN']}]}} if 'query' in url else {}
            return httpx.Response(200,json=body,request=httpx.Request('GET',url))
    monkeypatch.setattr(main.httpx,'AsyncClient',lambda **kw:Online())
    d=client.get('/dashboard/overview').json()
    assert all(d['services'].values());assert d['metrics']['p95'] is None
