import json
from pathlib import Path
import pandas as pd
from sqlalchemy import select
from app.database import Base, engine, SessionLocal
from app.models_db import Station, FeatureSnapshot
from app.services.inference import REGISTRY

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
FILES = {
    "ganga": DATA_DIR / "ganga_water_quality_weather.csv",
    "yamuna": DATA_DIR / "yamuna_water_quality_weather.csv",
}

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    summary = {}
    try:
        # Make the importer safe to run before the API has completed startup seeding.
        seed_path = DATA_DIR / "stations_seed.json"
        if seed_path.exists():
            for item in json.loads(seed_path.read_text(encoding="utf-8")):
                found = db.query(Station).filter_by(
                    river=item["river"], name=item["name"]
                ).first()
                if found is None:
                    db.add(Station(**item))
            db.commit()

        for river, path in FILES.items():
            if not path.exists():
                raise FileNotFoundError(f"Missing dataset: {path}")
            df = pd.read_csv(path)
            df["Data Acquisition Time"] = pd.to_datetime(
                df["Data Acquisition Time"], errors="coerce"
            )
            df = df.dropna(subset=["Station", "Data Acquisition Time"])
            required = sorted({
                feature
                for target_meta in REGISTRY[river].values()
                for feature in target_meta["features"]
            })
            missing_columns = [c for c in required if c not in df.columns]
            if missing_columns:
                raise ValueError(f"{river}: dataset missing model columns: {missing_columns}")

            imported = skipped = 0
            for _, row in df.iterrows():
                station_name = str(row["Station"]).strip()
                station = db.query(Station).filter_by(
                    river=river.title(), name=station_name
                ).first()
                if station is None:
                    skipped += 1
                    continue
                observed_at = row["Data Acquisition Time"].to_pydatetime()
                exists = db.query(FeatureSnapshot).filter_by(
                    station_id=station.id, observed_at=observed_at
                ).first()
                if exists:
                    skipped += 1
                    continue
                features = {}
                for col in required:
                    value = row[col]
                    features[col] = None if pd.isna(value) else (
                        value.item() if hasattr(value, "item") else value
                    )
                actuals = {}
                for target, col in {
                    "BOD": "Biochemical Oxygen Demand (mg/L)",
                    "DO": "Dissolved oxygen (mg/L)",
                    "pH": "Potential of Hydrogen (pH)",
                }.items():
                    if col in row and pd.notna(row[col]):
                        actuals[target] = float(row[col])
                db.add(FeatureSnapshot(
                    station_id=station.id,
                    observed_at=observed_at,
                    features=features,
                    actuals=actuals,
                    source="AQUA notebook engineered historical dataset",
                ))
                imported += 1
            db.commit()
            summary[river] = {"imported": imported, "skipped_or_unmatched": skipped}
        print(json.dumps(summary, indent=2))
    finally:
        db.close()

if __name__ == "__main__":
    main()
