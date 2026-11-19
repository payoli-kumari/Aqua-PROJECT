# AQUA application architecture (initial)

Browser dashboard -> FastAPI -> inference service -> river/target model registry -> serialized sklearn pipelines.
FastAPI -> SQLAlchemy -> SQLite by default (PostgreSQL configurable).
Prediction results -> provisional alert screening -> persisted predictions and alerts.

## Deliberate boundaries
- The trained pipelines and their exact feature order are preserved.
- Input feature engineering is not silently recreated in the API. The API accepts the exact engineered feature vector expected by each model.
- Automated ingestion from CWC/Open-Meteo, temporal lag construction, and weather aggregation are the next integration milestone.
- Alert thresholds are provisional screening rules, not a claim of CPCB compliance.
