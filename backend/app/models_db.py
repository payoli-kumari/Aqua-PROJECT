from sqlalchemy import String, Float, DateTime, ForeignKey, Text, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from .database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Station(Base):
    __tablename__ = "stations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    river: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    observations = relationship("Observation", back_populates="station")
    predictions = relationship("Prediction", back_populates="station")

class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    values: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(80), default="manual/API")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    station = relationship("Station", back_populates="observations")

class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    input_observation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    results: Mapped[dict] = mapped_column(JSON)
    model_versions: Mapped[dict] = mapped_column(JSON)
    station = relationship("Station", back_populates="predictions")

class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id"), nullable=True)
    parameter: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    station = relationship("Station")


class FeatureSnapshot(Base):
    """Model-ready feature row derived by the AQUA research data pipeline."""
    __tablename__ = "feature_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    features: Mapped[dict] = mapped_column(JSON)
    actuals: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(120), default="AQUA engineered historical dataset")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    station = relationship("Station")
