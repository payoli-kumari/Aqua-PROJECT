import json, joblib, warnings
from functools import lru_cache
from pathlib import Path
import pandas as pd
from ..config import MODEL_DIR

REGISTRY = json.loads((MODEL_DIR / "registry.json").read_text(encoding="utf-8"))

@lru_cache(maxsize=None)
def load_payload(filename: str):
    # scikit-learn warns when model serialization version differs.
    # The project's requirements pin the training version to reduce this risk.
    with warnings.catch_warnings():
        warnings.simplefilter("default")
        return joblib.load(MODEL_DIR / filename)

def predict_all(river: str, station: str, features: dict):
    key = river.strip().lower()
    if key not in REGISTRY:
        raise ValueError("river must be Ganga or Yamuna")
    results, versions = {}, {}
    for target, meta in REGISTRY[key].items():
        missing = [f for f in meta["features"] if f not in features]
        if missing:
            raise ValueError(f"{river} {target} is missing {len(missing)} required features: {missing[:8]}")
        row = pd.DataFrame([{f: features[f] for f in meta["features"]}], columns=meta["features"])
        payload = load_payload(meta["artifact"])
        value = float(payload["pipeline"].predict(row)[0])
        results[target] = {"value": value, "unit": "mg/L" if target in ("BOD","DO") else "pH"}
        versions[target] = {
            "model": meta["selected_model"],
            "experiment": meta["experiment"],
            "artifact": meta["artifact"]
        }
    return results, versions

def required_features(river: str):
    key = river.strip().lower()
    if key not in REGISTRY:
        raise ValueError("river must be Ganga or Yamuna")
    return {target: meta["features"] for target, meta in REGISTRY[key].items()}
