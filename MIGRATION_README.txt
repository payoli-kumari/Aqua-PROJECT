AQUA COMPLETE EVALUATION BUILD

This package contains the complete Feature Pipeline + Ganga Evaluation application.

IMPORTANT DATABASE MIGRATION
The runtime database aqua.db is intentionally excluded so you do not accidentally overwrite your latest local database.
Before starting the new build, copy your existing aqua.db from your current backend\data folder into this build's backend\data folder.

Keep a backup copy of aqua.db. Do not delete your old project folders until the new build starts and you verify your snapshots/predictions.

The app includes the Ganga evaluation endpoint GET /api/evaluation/ganga and the updated frontend.
