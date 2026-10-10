from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from xgboost import XGBRegressor

from sklearn.preprocessing import MinMaxScaler

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping


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

MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ==================================================
# LOAD DATA
# ==================================================

print("Loading processed dataset...")

df = pd.read_csv(
    DATA_PATH,
    index_col=0,
    parse_dates=True
)

df = df.sort_index()

print(f"Dataset shape: {df.shape}")


# ==================================================
# FEATURES FOR RANDOM FOREST / XGBOOST
# ==================================================

FEATURES = [
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_6",
    "lag_12",
    "lag_24",
    "lag_48",
    "lag_168",
    "rolling_mean_24",
    "rolling_std_24",
    "rolling_mean_168",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "is_weekend",
    "month",
]

TARGET = "energy_kwh"


# ==================================================
# CHRONOLOGICAL SPLIT
# ==================================================

n = len(df)

train_end = int(n * 0.70)
validation_end = int(n * 0.85)

train_df = df.iloc[:train_end]

validation_df = df.iloc[
    train_end:validation_end
]

test_df = df.iloc[
    validation_end:
]

print("\nData split:")
print(f"Training:   {len(train_df):,}")
print(f"Validation: {len(validation_df):,}")
print(f"Testing:    {len(test_df):,}")


# ==================================================
# RANDOM FOREST
# ==================================================

print("\nTraining Random Forest...")

X_train = train_df[FEATURES]
y_train = train_df[TARGET]

X_test = test_df[FEATURES]
y_test = test_df[TARGET]

rf = RandomForestRegressor(
    n_estimators=250,
    max_depth=20,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1
)

rf.fit(X_train, y_train)

rf_predictions = rf.predict(X_test)

rf_mae = mean_absolute_error(
    y_test,
    rf_predictions
)

rf_rmse = np.sqrt(
    mean_squared_error(
        y_test,
        rf_predictions
    )
)

rf_r2 = r2_score(
    y_test,
    rf_predictions
)

print("\nRandom Forest results:")
print(f"MAE:  {rf_mae:.4f}")
print(f"RMSE: {rf_rmse:.4f}")
print(f"R²:   {rf_r2:.4f}")

joblib.dump(
    rf,
    MODEL_DIR / "random_forest.joblib"
)


# ==================================================
# XGBOOST
# ==================================================

print("\nTraining XGBoost...")

xgb = XGBRegressor(
    n_estimators=500,
    max_depth=8,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="reg:squarederror",
    random_state=42,
    n_jobs=4
)

xgb.fit(
    X_train,
    y_train
)

xgb_predictions = xgb.predict(X_test)

xgb_mae = mean_absolute_error(
    y_test,
    xgb_predictions
)

xgb_rmse = np.sqrt(
    mean_squared_error(
        y_test,
        xgb_predictions
    )
)

xgb_r2 = r2_score(
    y_test,
    xgb_predictions
)

print("\nXGBoost results:")
print(f"MAE:  {xgb_mae:.4f}")
print(f"RMSE: {xgb_rmse:.4f}")
print(f"R²:   {xgb_r2:.4f}")

joblib.dump(
    xgb,
    MODEL_DIR / "xgboost.joblib"
)


# ==================================================
# LSTM DATA
# ==================================================

print("\nPreparing LSTM data...")

energy_values = df[TARGET].values.reshape(-1, 1)

scaler = MinMaxScaler()

scaler.fit(
    train_df[[TARGET]]
)

scaled_values = scaler.transform(
    df[[TARGET]]
)


def create_sequences(
    data,
    timestamps,
    sequence_length=24
):
    X = []
    y = []
    time_values = []

    for i in range(
        sequence_length,
        len(data)
    ):
        X.append(
            data[
                i - sequence_length:i
            ]
        )

        y.append(
            data[i]
        )

        time_values.append(
            timestamps[i]
        )

    return (
        np.array(X),
        np.array(y),
        time_values
    )


timestamps = df.index

X_lstm, y_lstm, lstm_times = create_sequences(
    scaled_values,
    timestamps,
    sequence_length=24
)


# ==================================================
# LSTM SPLIT
# ==================================================

lstm_train_end = train_end - 24
lstm_validation_end = validation_end - 24

X_lstm_train = X_lstm[:lstm_train_end]
y_lstm_train = y_lstm[:lstm_train_end]

X_lstm_val = X_lstm[
    lstm_train_end:lstm_validation_end
]

y_lstm_val = y_lstm[
    lstm_train_end:lstm_validation_end
]

X_lstm_test = X_lstm[
    lstm_validation_end:
]

y_lstm_test = y_lstm[
    lstm_validation_end:
]

print(
    f"LSTM training sequences: {len(X_lstm_train):,}"
)

print(
    f"LSTM validation sequences: {len(X_lstm_val):,}"
)

print(
    f"LSTM testing sequences: {len(X_lstm_test):,}"
)


# ==================================================
# LSTM MODEL
# ==================================================

print("\nBuilding LSTM model...")

lstm = Sequential(
    [
        LSTM(
            64,
            input_shape=(
                X_lstm_train.shape[1],
                X_lstm_train.shape[2]
            )
        ),

        Dropout(0.2),

        Dense(
            32,
            activation="relu"
        ),

        Dense(1)
    ]
)

lstm.compile(
    optimizer="adam",
    loss="mse",
    metrics=["mae"]
)


# ==================================================
# EARLY STOPPING
# ==================================================

early_stopping = EarlyStopping(
    monitor="val_loss",
    patience=5,
    restore_best_weights=True
)


# ==================================================
# TRAIN LSTM
# ==================================================

print("\nTraining LSTM...")

history = lstm.fit(
    X_lstm_train,
    y_lstm_train,
    validation_data=(
        X_lstm_val,
        y_lstm_val
    ),
    epochs=30,
    batch_size=64,
    callbacks=[early_stopping],
    verbose=1
)


# ==================================================
# LSTM PREDICTION
# ==================================================

lstm_scaled_predictions = lstm.predict(
    X_lstm_test,
    verbose=0
)

lstm_predictions = scaler.inverse_transform(
    lstm_scaled_predictions
).flatten()

lstm_actual = scaler.inverse_transform(
    y_lstm_test
).flatten()


# ==================================================
# LSTM METRICS
# ==================================================

lstm_mae = mean_absolute_error(
    lstm_actual,
    lstm_predictions
)

lstm_rmse = np.sqrt(
    mean_squared_error(
        lstm_actual,
        lstm_predictions
    )
)

lstm_r2 = r2_score(
    lstm_actual,
    lstm_predictions
)

print("\nLSTM results:")
print(f"MAE:  {lstm_mae:.4f}")
print(f"RMSE: {lstm_rmse:.4f}")
print(f"R²:   {lstm_r2:.4f}")


# ==================================================
# SAVE LSTM
# ==================================================

lstm.save(
    MODEL_DIR / "lstm.keras"
)

joblib.dump(
    scaler,
    MODEL_DIR / "lstm_scaler.joblib"
)


# ==================================================
# SAVE RESULTS
# ==================================================

results = {
    "Random Forest": {
        "MAE": float(rf_mae),
        "RMSE": float(rf_rmse),
        "R2": float(rf_r2)
    },

    "XGBoost": {
        "MAE": float(xgb_mae),
        "RMSE": float(xgb_rmse),
        "R2": float(xgb_r2)
    },

    "LSTM": {
        "MAE": float(lstm_mae),
        "RMSE": float(lstm_rmse),
        "R2": float(lstm_r2)
    }
}


with open(
    MODEL_DIR / "model_results.json",
    "w"
) as f:

    json.dump(
        results,
        f,
        indent=4
    )


# ==================================================
# SAVE TEST PREDICTIONS
# ==================================================

prediction_df = pd.DataFrame(
    {
        "actual": lstm_actual,
        "lstm_prediction": lstm_predictions
    },
    index=lstm_times[
        lstm_validation_end:
    ]
)

prediction_df.to_csv(
    MODEL_DIR / "lstm_predictions.csv"
)


print("\n========================================")
print("ALL MODELS TRAINED SUCCESSFULLY")
print("========================================")

print(json.dumps(
    results,
    indent=4
))