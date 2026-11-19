from pathlib import Path
import os
BASE_DIR = Path(__file__).resolve().parents[1]
APP_DIR = Path(__file__).resolve().parent
MODEL_DIR = APP_DIR / "models"
DATA_DIR = BASE_DIR / "data"
DATABASE_URL = os.getenv("AQUA_DATABASE_URL", f"sqlite:///{(DATA_DIR / 'aqua.db').as_posix()}")
CORS_ORIGINS = os.getenv("AQUA_CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000").split(",")
