from pathlib import Path

import joblib
import pandas as pd

from sklearn.ensemble import IsolationForest


# ==================================================
# PATHS
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "hourly_energy.csv"
)

MODEL_DIR = PROJECT_ROOT / "ml" / "models"

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ==================================================
# LOAD DATA
# ==================================================

df = pd.read_csv(
    DATA_PATH,
    index_col=0,
    parse_dates=True
)

df = df.sort_index()


# ==================================================
# FEATURES
# ==================================================

features = [
    "energy_kwh",
    "rolling_mean_24",
    "rolling_std_24"
]

X = df[features].copy()


# ==================================================
# TRAINING DATA
# ==================================================

train_size = int(
    len(X) * 0.70
)

X_train = X.iloc[:train_size]


# ==================================================
# ISOLATION FOREST
# ==================================================

print("Training Isolation Forest...")

model = IsolationForest(
    n_estimators=200,
    contamination=0.01,
    random_state=42,
    n_jobs=-1
)

model.fit(X_train)


# ==================================================
# DETECT ANOMALIES
# ==================================================

df["anomaly_score"] = model.decision_function(X)

df["anomaly"] = (
    model.predict(X) == -1
)


# ==================================================
# SAVE
# ==================================================

output_columns = [
    "energy_kwh",
    "anomaly_score",
    "anomaly"
]

df[output_columns].to_csv(
    MODEL_DIR / "anomalies.csv"
)

joblib.dump(
    model,
    MODEL_DIR / "isolation_forest.joblib"
)


print("\n========================================")
print("ANOMALY DETECTION COMPLETED")
print("========================================")

print(
    f"Anomalies detected: {df['anomaly'].sum():,}"
)

print(
    f"Saved to: {MODEL_DIR / 'anomalies.csv'}"
)