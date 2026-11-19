from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any

class ObservationIn(BaseModel):
    river: str
    station: str
    observed_at: datetime
    values: dict[str, float | None]
    source: str = "manual/API"

class PredictIn(BaseModel):
    river: str
    station: str
    observed_at: datetime | None = None
    features: dict[str, Any] = Field(..., description="Exact feature names required by the selected river/target model")

class AlertStatusIn(BaseModel):
    status: str


class HistoricalImportIn(BaseModel):
    replace_existing: bool = False


class PredictLatestIn(BaseModel):
    river: str
    station: str
