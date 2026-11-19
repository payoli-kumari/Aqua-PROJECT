"""Backfill missing Ganga actuals from original CWC UP biological/chemical CSVs.

Only exact Station + Data Acquisition Time matches are applied.
Existing non-null actual values are never overwritten.
Run from backend folder:
    .\.venv\Scripts\python.exe -m app.scripts.backfill_ganga_actuals
"""
from pathlib import Path
import json
import pandas as pd

from app.database import SessionLocal
from app.models_db import Station, FeatureSnapshot

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BIO_FILE = DATA_DIR / "swq_biological_parameter_manual_cwc_up_2021_2025.csv"
CHEM_FILE = DATA_DIR / "swq_chemical_parameter_manual_cwc_up_2021_2025.csv"

def load_source(path: Path, wanted: dict[str, str]) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required CWC source file not found: {path}")
    df = pd.read_csv(path, low_memory=False)
    required = {"Station", "River", "Data Acquisition Time", *wanted.values()}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{path.name} is missing columns: {missing}")

    df = df[df["River"].astype(str).str.strip().str.casefold() == "ganga"].copy()
    df["__station_key"] = df["Station"].astype(str).str.strip().str.upper()
    df["__observed_at"] = pd.to_datetime(
        df["Data Acquisition Time"], dayfirst=True, errors="coerce"
    )
    df = df.dropna(subset=["__observed_at", "__station_key"])

    # Fail safely if a source has duplicate station-time keys: do not choose arbitrarily.
    duplicates = df.duplicated(["__station_key", "__observed_at"], keep=False)
    if duplicates.any():
        examples = df.loc[duplicates, ["Station", "Data Acquisition Time"]].head(10)
        raise ValueError(
            f"Duplicate station/time keys in {path.name}; resolve before backfill:\n"
            + examples.to_string(index=False)
        )

    result = {}
    for _, row in df.iterrows():
        values = {}
        for target, column in wanted.items():
            value = pd.to_numeric(row[column], errors="coerce")
            if pd.notna(value):
                values[target] = float(value)
        result[(row["__station_key"], row["__observed_at"].to_pydatetime())] = values
    return result

def main():
    bio = load_source(BIO_FILE, {
        "BOD": "Biochemical Oxygen Demand (mg/L)"
    })
    chem = load_source(CHEM_FILE, {
        "DO": "Dissolved oxygen (mg/L)",
        "pH": "Potential of Hydrogen (pH)"
    })

    db = SessionLocal()
    try:
        snapshots = (
            db.query(FeatureSnapshot)
            .join(Station, FeatureSnapshot.station_id == Station.id)
            .filter(Station.river == "Ganga")
            .all()
        )
        summary = {
            "ganga_snapshots_checked": len(snapshots),
            "exact_station_timestamp_matches": 0,
            "snapshots_updated": 0,
            "values_added": {"BOD": 0, "DO": 0, "pH": 0},
            "complete_actuals_after_backfill": 0,
            "unmatched_snapshots": 0,
        }

        for snapshot in snapshots:
            station_key = snapshot.station.name.strip().upper()
            observed_at = snapshot.observed_at.replace(tzinfo=None) if snapshot.observed_at.tzinfo else snapshot.observed_at
            key = (station_key, observed_at)
            bio_values = bio.get(key)
            chem_values = chem.get(key)
            if bio_values is None and chem_values is None:
                summary["unmatched_snapshots"] += 1
                continue

            summary["exact_station_timestamp_matches"] += 1
            actuals = dict(snapshot.actuals or {})
            before = dict(actuals)

            for source_values in (bio_values or {}, chem_values or {}):
                for target, value in source_values.items():
                    if actuals.get(target) is None:
                        actuals[target] = value
                        summary["values_added"][target] += 1

            if actuals != before:
                snapshot.actuals = actuals
                snapshot.source = (
                    (snapshot.source or "AQUA engineered historical dataset")
                    + " | actuals exact-matched from CWC UP 2021-2025"
                )[:120]
                summary["snapshots_updated"] += 1

            if all(actuals.get(k) is not None for k in ("BOD", "DO", "pH")):
                summary["complete_actuals_after_backfill"] += 1

        db.commit()
        print(json.dumps(summary, indent=2))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
