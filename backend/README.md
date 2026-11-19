# AQUA Backend (initial integration build)

## Run on Windows
1. Open terminal in `backend`.
2. Run `run.bat` (first run installs dependencies).
3. Open http://127.0.0.1:8000/docs

## Main routes
- `GET /health`
- `GET /api/rivers`
- `GET /api/stations?river=Ganga`
- `GET /api/models`
- `GET /api/features/{river}`
- `GET /api/feature-snapshots/latest?river=Ganga&station=Allahabad`
- `POST /api/predict/latest`
- `POST /api/observations`
- `POST /api/predict`
- `GET /api/predictions`
- `GET /api/alerts`

## Prediction contract
`POST /api/predict` expects `river`, exact `station` name, optional `observed_at`, and a `features` object containing every feature required by all three target models for that river. Call `GET /api/features/{river}` to retrieve exact names.

## Important limitations
- SQLite is used for a zero-setup local prototype. PostgreSQL can be configured through `AQUA_DATABASE_URL`.
- Weather feature values must currently be supplied by the caller. Automated weather ingestion and lag/rolling feature construction are not implemented yet.
- Alert thresholds in `app/services/alerts.py` are provisional screening values and require supervisor/standard verification before being treated as regulatory thresholds.
- Model artifacts were serialized with scikit-learn 1.9.1. Keep that version pinned. Loading with a different scikit-learn version may produce warnings or compatibility problems.
- This is a research prototype; predictions are not regulatory determinations and do not replace laboratory testing.


## Import AQUA historical model-ready feature rows

The app now includes the engineered Ganga and Yamuna datasets generated during the AQUA notebook experiments. These are imported into a dedicated `feature_snapshots` table (not mixed with raw observations).

With the backend virtual environment active, from the `backend` folder run:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.import_historical
```

Restart the API after the import. Then use:

- `GET /api/feature-snapshots/latest?river=Ganga&station=Allahabad`
- `POST /api/predict/latest` with `{"river":"Ganga","station":"Allahabad"}`

The prediction response includes the historical actual values for comparison and clearly identifies the run as `historical_replay`.

Important: this milestone uses the already-engineered historical rows from the research notebooks. It does **not** yet create new features from a newly submitted raw CWC observation or fetch live weather. That next step requires reproducing and validating the notebook feature-generation rules before enabling live forecasts. Missing values are preserved as null; no blanket imputation is performed by the importer.
