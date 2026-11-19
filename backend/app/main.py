from pathlib import Path
import json
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc
from .config import CORS_ORIGINS, DATA_DIR
from .database import Base, engine, get_db
from .models_db import Station, Observation, Prediction, Alert, FeatureSnapshot
from .schemas import ObservationIn, PredictIn, PredictLatestIn, AlertStatusIn
from .services.inference import predict_all, required_features, REGISTRY
from .services.alerts import assess

app = FastAPI(title="AQUA API", version="0.1.0",
              description="AI-based Quality Understanding and Analytics")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    seed_file = DATA_DIR / "stations_seed.json"
    if seed_file.exists():
        db = next(get_db())
        try:
            for item in json.loads(seed_file.read_text(encoding="utf-8")):
                exists = db.query(Station).filter_by(river=item["river"], name=item["name"]).first()
                if not exists:
                    db.add(Station(**item))
            db.commit()
        finally:
            db.close()

@app.get("/health")
def health():
    return {"status": "ok", "service": "AQUA API"}

@app.get("/api")
def api_info():
    return {"name": "AQUA", "version": app.version, "rivers": list(REGISTRY.keys()),
            "targets": ["BOD", "DO", "pH"]}

@app.get("/api/models")
def models():
    return REGISTRY

@app.get("/api/rivers")
def rivers():
    return [{"id": "ganga", "name": "Ganga"}, {"id": "yamuna", "name": "Yamuna"}]

@app.get("/api/stations")
def stations(river: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Station)
    if river:
        q = q.filter(Station.river.ilike(river))
    return [{"id":s.id,"river":s.river,"name":s.name,"latitude":s.latitude,"longitude":s.longitude}
            for s in q.order_by(Station.river, Station.name).all()]

@app.get("/api/features/{river}")
def features(river: str):
    try: return required_features(river)
    except ValueError as e: raise HTTPException(400, str(e))

@app.post("/api/observations", status_code=201)
def create_observation(payload: ObservationIn, db: Session = Depends(get_db)):
    station = db.query(Station).filter_by(river=payload.river.title(), name=payload.station).first()
    if not station: raise HTTPException(404, "Station not found for this river")
    row = Observation(station_id=station.id, observed_at=payload.observed_at,
                      values=payload.values, source=payload.source)
    db.add(row); db.commit(); db.refresh(row)
    return {"id":row.id,"station_id":station.id,"observed_at":row.observed_at,"values":row.values}

@app.get("/api/observations")
def list_observations(river: str | None = None, station: str | None = None,
                      limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(Observation).join(Station)
    if river: q = q.filter(Station.river.ilike(river))
    if station: q = q.filter(Station.name == station)
    rows = q.order_by(desc(Observation.observed_at)).limit(min(limit,500)).all()
    return [{"id":r.id,"river":r.station.river,"station":r.station.name,
             "observed_at":r.observed_at,"values":r.values,"source":r.source} for r in rows]


@app.get("/api/feature-snapshots/latest")
def latest_features(river: str, station: str, db: Session = Depends(get_db)):
    """Return the newest imported model-ready feature row for a station."""
    station_row = db.query(Station).filter_by(
        river=river.title(), name=station
    ).first()
    if not station_row:
        raise HTTPException(404, "Station not found")
    snapshot = db.query(FeatureSnapshot).filter_by(
        station_id=station_row.id
    ).order_by(desc(FeatureSnapshot.observed_at)).first()
    if not snapshot:
        raise HTTPException(
            404,
            "No historical feature rows found. Import the AQUA historical datasets first."
        )
    return {
        "river": station_row.river,
        "station": station_row.name,
        "observed_at": snapshot.observed_at,
        "features": snapshot.features,
        "actuals": snapshot.actuals,
        "source": snapshot.source,
        "note": "Historical engineered feature row from the AQUA research dataset; not a live sensor reading."
    }


@app.post("/api/predict/latest")
def predict_latest(payload: PredictLatestIn, db: Session = Depends(get_db)):
    """Run all three selected models using the latest imported feature snapshot."""
    station_row = db.query(Station).filter_by(
        river=payload.river.title(), name=payload.station
    ).first()
    if not station_row:
        raise HTTPException(404, "Station not found. Check /api/stations.")
    snapshot = db.query(FeatureSnapshot).filter_by(
        station_id=station_row.id
    ).order_by(desc(FeatureSnapshot.observed_at)).first()
    if not snapshot:
        raise HTTPException(
            404,
            "No historical feature rows found. Run: python -m app.scripts.import_historical"
        )
    try:
        results, versions = predict_all(
            payload.river, payload.station, snapshot.features
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    generated_alerts = assess(results)
    prediction = Prediction(
        station_id=station_row.id,
        input_observation_at=snapshot.observed_at,
        results=results,
        model_versions=versions
    )
    db.add(prediction)
    db.flush()
    for item in generated_alerts:
        db.add(Alert(
            station_id=station_row.id,
            prediction_id=prediction.id,
            parameter=item["parameter"],
            severity=item["severity"],
            message=item["message"]
        ))
    db.commit()
    db.refresh(prediction)
    return {
        "prediction_id": prediction.id,
        "river": station_row.river,
        "station": station_row.name,
        "feature_snapshot_at": snapshot.observed_at,
        "predicted_at": prediction.predicted_at,
        "results": results,
        "actuals_for_comparison": snapshot.actuals,
        "model_versions": versions,
        "alerts": generated_alerts,
        "data_mode": "historical_replay",
        "disclaimer": "Historical model replay using pre-engineered AQUA research features. Not a live forecast, regulatory determination, or substitute for laboratory testing."
    }


@app.get("/api/evaluation/ganga")
def ganga_evaluation(target: str = "BOD", station: str | None = None):
    """Return held-out 2025 test evaluation for AQUA's selected Ganga models."""
    import pandas as pd
    target = target.upper()
    if target not in ("BOD", "DO", "PH"):
        raise HTTPException(400, "target must be BOD, DO, or pH")
    target = "pH" if target == "PH" else target
    prediction_file = DATA_DIR / "ganga_2025_test_predictions.csv"
    metrics_file = DATA_DIR / "ganga_2025_test_metrics.csv"
    if not prediction_file.exists() or not metrics_file.exists():
        raise HTTPException(503, "Ganga 2025 evaluation files are missing from backend/data")
    try:
        predictions = pd.read_csv(prediction_file)
        metrics = pd.read_csv(metrics_file)
        selected_experiment = {"BOD": "Baseline", "DO": "Weather", "pH": "Weather"}[target]
        subset = predictions[(predictions["Target"] == target) &
                             (predictions["Experiment"] == selected_experiment)].copy()
        actual_column = {"BOD": "target_BOD", "DO": "target_DO", "pH": "target_pH"}[target]
        subset = subset.dropna(subset=[actual_column, "Prediction"])
        if station:
            subset = subset[subset["Station"].astype(str).str.casefold() == station.casefold()]
        metric_row = metrics[(metrics["Target"] == target) &
                             (metrics["Experiment"] == selected_experiment)]
        if metric_row.empty:
            raise HTTPException(500, "Selected model metrics not found in evaluation file")
        m = metric_row.iloc[0]
        station_rows = []
        for station_name, group in subset.groupby("Station"):
            actual = group[actual_column].astype(float)
            predicted = group["Prediction"].astype(float)
            errors = predicted - actual
            mae = float(errors.abs().mean())
            rmse = float((errors.pow(2).mean()) ** 0.5)
            denominator = float(((actual - actual.mean()) ** 2).sum())
            r2 = None if denominator == 0 else float(1 - (errors.pow(2).sum() / denominator))
            station_rows.append({"station": str(station_name), "n": int(len(group)),
                                 "mae": mae, "rmse": rmse, "r2": r2})
        station_rows.sort(key=lambda x: x["station"].casefold())
        sample = [{"station": str(row["Station"]), "date": str(row["Date"]),
                   "actual": float(row[actual_column]), "predicted": float(row["Prediction"])}
                  for _, row in subset.sort_values(["Date", "Station"]).head(100).iterrows()]
        return {
            "river": "Ganga", "target": target, "experiment": selected_experiment,
            "model": str(m["Selected_Model"]), "evaluation_period": "2025 held-out test set",
            "n": int(m["Test_N"]), "mae": float(m["Test_MAE"]),
            "rmse": float(m["Test_RMSE"]), "r2": float(m["Test_R2"]),
            "persistence_baseline": {"n": int(m["Persistence_N"]),
                                     "mae": float(m["Persistence_MAE"]),
                                     "rmse": float(m["Persistence_RMSE"]),
                                     "r2": float(m["Persistence_R2"])},
            "station_count_in_test_rows": int(predictions[predictions["Target"] == target]["Station"].nunique()),
            "station_metrics": station_rows, "observations": sample,
            "scope_note": "Metrics are from the original held-out 2025 research test set. Station metrics are recalculated from selected-model test predictions. This is not a live evaluation."
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Could not load Ganga evaluation data: {e}")

@app.post("/api/predict")
def predict(payload: PredictIn, db: Session = Depends(get_db)):
    station = db.query(Station).filter_by(river=payload.river.title(), name=payload.station).first()
    if not station: raise HTTPException(404, "Station not found. Check /api/stations.")
    try:
        results, versions = predict_all(payload.river, payload.station, payload.features)
    except ValueError as e:
        raise HTTPException(422, str(e))
    generated_alerts = assess(results)
    prediction = Prediction(station_id=station.id, input_observation_at=payload.observed_at,
                            results=results, model_versions=versions)
    db.add(prediction); db.flush()
    for item in generated_alerts:
        db.add(Alert(station_id=station.id, prediction_id=prediction.id,
                     parameter=item["parameter"], severity=item["severity"], message=item["message"]))
    db.commit(); db.refresh(prediction)
    return {"prediction_id":prediction.id,"river":station.river,"station":station.name,
            "predicted_at":prediction.predicted_at,"results":results,"model_versions":versions,
            "alerts":generated_alerts,
            "disclaimer":"Research prototype predictions; not a regulatory determination or substitute for laboratory testing."}

@app.get("/api/predictions")
def list_predictions(river: str | None = None, station: str | None = None,
                     limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(Prediction).join(Station)
    if river: q = q.filter(Station.river.ilike(river))
    if station: q = q.filter(Station.name == station)
    rows = q.order_by(desc(Prediction.predicted_at)).limit(min(limit,200)).all()
    return [{"id":r.id,"river":r.station.river,"station":r.station.name,
             "predicted_at":r.predicted_at,"results":r.results,"model_versions":r.model_versions}
            for r in rows]

@app.get("/api/alerts")
def list_alerts(status: str | None = "open", db: Session = Depends(get_db)):
    q = db.query(Alert)
    if status: q=q.filter(Alert.status == status)
    rows=q.order_by(desc(Alert.created_at)).limit(200).all()
    return [{"id":r.id,"station":r.station.name,"river":r.station.river,
             "parameter":r.parameter,"severity":r.severity,"message":r.message,
             "status":r.status,"created_at":r.created_at} for r in rows]

@app.patch("/api/alerts/{alert_id}")
def update_alert(alert_id: int, payload: AlertStatusIn, db: Session = Depends(get_db)):
    if payload.status not in ("open","acknowledged","resolved"):
        raise HTTPException(400, "status must be open, acknowledged, or resolved")
    row=db.query(Alert).filter_by(id=alert_id).first()
    if not row: raise HTTPException(404, "Alert not found")
    row.status=payload.status; db.commit()
    return {"id":row.id,"status":row.status}
