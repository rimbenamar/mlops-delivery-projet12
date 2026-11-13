import asyncio
import json
import logging
import os
import time
import math
from pathlib import Path
import httpx
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from collections import deque
from contextlib import asynccontextmanager
from threading import Lock
import mlflow
import mlflow.sklearn
import numpy as np
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from prometheus_client import Counter, Gauge, Histogram, CONTENT_TYPE_LATEST, generate_latest
from starlette.concurrency import run_in_threadpool
from app.domain import FEATURES, NAME, LABELS

requests = Counter("http_requests_total", "Total HTTP requests", ["method", "handler", "status"])
latency = Histogram("http_request_duration_seconds", "HTTP latency", ["method", "handler"],
                    buckets=(.001,.005,.01,.025,.05,.1,.25,.5,1,2,5))
pred_latency = Histogram("prediction_latency_seconds", "Model inference latency", buckets=(.001,.005,.01,.025,.05,.1,.25,.5,1,2))
predictions = Counter("predictions_total", "Predictions by class", ["class_name"])
drift = Gauge("data_drift_score", "Absolute window mean shift divided by training standard deviation", ["feature"])
drift_flag = Gauge("data_drift_detected", "One if any standardized shift exceeds threshold")
window_size = Gauge("data_drift_window_samples", "Samples in rolling drift window")
ready = Gauge("model_ready", "Whether model has loaded")
state = {}
window = deque(maxlen=200)
history = deque(maxlen=12)
lock = Lock()

@asynccontextmanager
async def lifespan(app):
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    def load():
        client = mlflow.MlflowClient()
        version = client.get_model_version_by_alias(NAME, "champion")
        model = mlflow.sklearn.load_model(f"models:/{NAME}/{version.version}")
        path = client.download_artifacts(version.run_id, "reference.json")
        with open(path) as f:
            reference = json.load(f)
        return {"model": model, "reference": reference, "version": str(version.version),
                "run_id": version.run_id, "training_metrics": client.get_run(version.run_id).data.metrics}
    state.update(await run_in_threadpool(load))
    ready.set(1)
    yield
    ready.set(0)

app = FastAPI(title="DeliveryOps — Mini-Projet 12", version="1.0.0", lifespan=lifespan)

@app.middleware("http")
async def instrument(request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        handler = getattr(route, "path", "unmatched")
        if handler != "/metrics":
            requests.labels(request.method, handler, str(status)).inc()
            latency.labels(request.method, handler).observe(time.perf_counter() - start)

class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    distance_km: float = Field(ge=0, le=6000, allow_inf_nan=False)
    weight_kg: float = Field(gt=0, le=100, allow_inf_nan=False)
    price_brl: float = Field(gt=0, le=30000, allow_inf_nan=False)
    freight_brl: float = Field(ge=0, le=5000, allow_inf_nan=False)
    promised_days: int = Field(ge=1, le=100)
    item_count: int = Field(ge=1, le=50)
    purchase_weekday: int = Field(ge=0, le=6, description="0 Monday, 6 Sunday")
    purchase_month: int = Field(ge=1, le=12)

class PredictResponse(BaseModel):
    class_id: int
    class_name: str
    delay_probability: float
    probabilities: list[float]
    decision_threshold: float
    model_version: str

@app.get("/health")
async def health():
    if "model" not in state:
        raise HTTPException(503, "Model unavailable")
    return {"status": "ok", "model_version": state["version"]}

@app.get("/model")
async def model_info():
    return {"name": NAME, "version": state["version"], "alias": "champion",
            "features": state["reference"]["features"], "drift_min_samples": 30, "drift_threshold": 1.5,
            "decision_threshold": state["reference"]["threshold"],
            "training_metrics": state.get("training_metrics",{}),
            "dataset": state["reference"].get("dataset",{}),
            "splits": state["reference"].get("splits",{}),
            "examples": state["reference"].get("examples",[]),
            "feature_importance": state["reference"].get("feature_importance",{})}

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})

def infer(row):
    start = time.perf_counter()
    try:
        model = state["model"]
        proba = model.predict_proba(row)[0]
        risk = float(proba[list(model.classes_).index(1)])
        index = int(risk >= state["reference"]["threshold"])
        reference = state["reference"]
        name = reference["classes"][index]
        predictions.labels(name).inc()
        with lock:
            window.append(row[0].copy())
            window_size.set(len(window))
            if len(window) >= 30:
                scores = np.abs(np.mean(window, axis=0)-np.array(reference["mean"])) / np.maximum(reference["std"], 1e-8)
                for feature, score in zip(reference["features"], scores):
                    drift.labels(feature).set(float(score))
                drift_flag.set(int(np.any(scores > 1.5)))
        result = {"class_id": index, "class_name": name, "delay_probability": risk, "probabilities": proba.tolist(), "decision_threshold": reference["threshold"], "model_version": state["version"]}
        with lock:
            history.appendleft({"time": time.strftime("%H:%M:%S",time.gmtime()), "distance_km":float(row[0][0]), "promised_days":int(row[0][4]), "risk":risk, "class_name":name})
        return result
    finally:
        pred_latency.observe(time.perf_counter() - start)

@app.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictRequest):
    row = np.array([[getattr(payload, f) for f in state["reference"]["features"]]])
    try:
        return await run_in_threadpool(infer, row)
    except Exception:
        logging.exception("Inference failed")
        raise HTTPException(500, "Inference failed")


STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(STATIC / "index.html")

@app.get("/dashboard/overview")
async def overview():
    urls = {
        "mlflow": os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000") + "/health",
        "prometheus": os.getenv("PROMETHEUS_URL", "http://localhost:9090") + "/-/ready",
        "grafana": os.getenv("GRAFANA_URL", "http://localhost:3000") + "/api/health",
    }
    queries = {
        "rps": 'sum(rate(http_requests_total{handler="/predict"}[1m]))',
        "p95": 'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{handler="/predict"}[1m])))',
        "p99": 'histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{handler="/predict"}[1m])))',
        "errors": 'sum(rate(http_requests_total{handler="/predict",status=~"5.."}[1m])) or vector(0)',
    }
    async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
        async def check(name,url):
            try:
                response = await client.get(url)
                return name, response.is_success
            except httpx.HTTPError:
                return name, False
        async def query(name, expr):
            try:
                response = await client.get(os.getenv("PROMETHEUS_URL", "http://localhost:9090") + "/api/v1/query", params={"query":expr})
                response.raise_for_status()
                values = response.json()["data"]["result"]
                value = float(values[0]["value"][1]) if values else None
                return name, value if value is not None and math.isfinite(value) else None
            except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
                return name, None
        results = await asyncio.gather(*(check(k,v) for k,v in urls.items()), *(query(k,v) for k,v in queries.items()))
    with lock:
        n = len(window)
        recent = list(history)
        reference = state["reference"]
        scores = (np.abs(np.mean(window,axis=0)-np.array(reference["mean"])) / np.maximum(reference["std"],1e-8)).tolist() if n>=30 else None
    return {
        "services": {"api": "model" in state, **dict(results[:3])},
        "metrics": dict(results[3:]),
        "model": {"name": NAME, "version": state["version"], "run_id": state.get("run_id"), "training_metrics": state.get("training_metrics",{}), "threshold": reference["threshold"], "dataset": reference.get("dataset",{}), "splits":reference.get("splits",{}), "feature_importance":reference.get("feature_importance",{})},
        "drift": {"samples": n, "minimum":30, "threshold":1.5, "scores": dict(zip(reference["features"],scores)) if scores else {}, "detected": any(v>1.5 for v in scores) if scores else None},
        "recent": recent,
        "predictions": sum(sample.value for metric in predictions.collect() for sample in metric.samples if sample.name=="predictions_total"),
    }


@app.get("/dashboard/traffic-sample")
async def traffic_sample():
    # Actual training-feature samples only, with no outcome labels exposed.
    return {"samples": state["reference"]["samples"], "features": FEATURES}
