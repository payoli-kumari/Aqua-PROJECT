# AQUA — initial full-stack integration

This build creates a first working application layer around the selected Ganga and Yamuna model artifacts.

## Structure
- `backend/`: FastAPI, SQLAlchemy persistence, model inference, alert screening.
- `frontend/`: lightweight browser dashboard.
- `docs/`: architecture and next implementation notes.

## Start
1. Open a terminal in `backend`.
2. Run `run.bat` on Windows.
3. Wait for dependency installation and server startup.
4. Open `http://127.0.0.1:8000/docs`.
5. In a second terminal, serve the frontend: `python -m http.server 5500 --directory ../frontend`.
6. Open `http://127.0.0.1:5500`.

See `backend/README.md` for API details and limitations.


## Historical feature replay milestone

The backend now ships with the notebook-engineered Ganga and Yamuna feature datasets. After the first dependency installation, stop the running API with `Ctrl+C`, then from the `backend` folder run:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.import_historical
```

Start the API again with ` .\run.bat `. In Swagger, use `POST /api/predict/latest` with a river and station name. This is a historical replay using already-engineered research rows, not a live forecast. See `backend/README.md` for details.


## Historical model evaluation milestone
The dashboard now includes a Ganga 2025 held-out test evaluation section. The API endpoint `GET /api/evaluation/ganga?target=BOD` supports BOD, DO and pH. It reports original aggregate test metrics and persistence baselines from the research metrics file, plus station-wise metrics recalculated from the selected model's test predictions. The supplied evaluation files are stored in `backend/data/`. This evaluation is separate from historical feature replay and is not a live/current assessment.
