from pathlib import Path
import pandas as pd
import numpy as np


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# FIND DATASET
# --------------------------------------------------

dataset_files = list(RAW_DIR.rglob("household_power_consumption.txt"))

if not dataset_files:
    raise FileNotFoundError(
        "Could not find household_power_consumption.txt inside data/raw"
    )

DATASET_PATH = dataset_files[0]

print(f"Dataset found at: {DATASET_PATH}")


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

print("\nLoading dataset...")

df = pd.read_csv(
    DATASET_PATH,
    sep=";",
    na_values="?",
    low_memory=False
)

print(f"Original rows: {len(df):,}")
print(f"Original columns: {len(df.columns)}")


# --------------------------------------------------
# CREATE TIMESTAMP
# --------------------------------------------------

df["timestamp"] = pd.to_datetime(
    df["Date"] + " " + df["Time"],
    dayfirst=True,
    errors="coerce"
)

df = df.drop(columns=["Date", "Time"])

df = df.set_index("timestamp")

df = df.sort_index()


# --------------------------------------------------
# CONVERT POWER COLUMN
# --------------------------------------------------

df["Global_active_power"] = pd.to_numeric(
    df["Global_active_power"],
    errors="coerce"
)


# --------------------------------------------------
# HANDLE MISSING VALUES
# --------------------------------------------------

missing_before = df["Global_active_power"].isna().sum()

print(f"Missing power values before processing: {missing_before:,}")

df["Global_active_power"] = (
    df["Global_active_power"]
    .interpolate(method="time", limit=120)
    .ffill()
    .bfill()
)

missing_after = df["Global_active_power"].isna().sum()

print(f"Missing power values after processing: {missing_after:,}")


# --------------------------------------------------
# RESAMPLE TO HOURLY ENERGY
# --------------------------------------------------
#
# Global_active_power is measured in kW.
#
# One-minute measurements:
#
# Energy (kWh) = Power (kW) × Time (hours)
#
# Therefore:
#
# hourly_energy = sum(minute_power) / 60
#
# --------------------------------------------------

hourly = (
    df["Global_active_power"]
    .resample("h")
    .sum()
    / 60.0
)

hourly = hourly.to_frame(name="energy_kwh")


# --------------------------------------------------
# CALENDAR FEATURES
# --------------------------------------------------

hourly["hour"] = hourly.index.hour

hourly["day_of_week"] = hourly.index.dayofweek

hourly["is_weekend"] = (
    hourly["day_of_week"] >= 5
).astype(int)

hourly["month"] = hourly.index.month


# --------------------------------------------------
# CYCLICAL TIME FEATURES
# --------------------------------------------------

hourly["hour_sin"] = np.sin(
    2 * np.pi * hourly["hour"] / 24
)

hourly["hour_cos"] = np.cos(
    2 * np.pi * hourly["hour"] / 24
)

hourly["dow_sin"] = np.sin(
    2 * np.pi * hourly["day_of_week"] / 7
)

hourly["dow_cos"] = np.cos(
    2 * np.pi * hourly["day_of_week"] / 7
)


# --------------------------------------------------
# LAG FEATURES
# --------------------------------------------------

lags = [
    1,
    2,
    3,
    6,
    12,
    24,
    48,
    168
]

for lag in lags:
    hourly[f"lag_{lag}"] = (
        hourly["energy_kwh"].shift(lag)
    )


# --------------------------------------------------
# ROLLING FEATURES
# --------------------------------------------------

hourly["rolling_mean_24"] = (
    hourly["energy_kwh"]
    .rolling(24)
    .mean()
)

hourly["rolling_std_24"] = (
    hourly["energy_kwh"]
    .rolling(24)
    .std()
)

hourly["rolling_mean_168"] = (
    hourly["energy_kwh"]
    .rolling(168)
    .mean()
)


# --------------------------------------------------
# REMOVE ROWS WITH MISSING FEATURES
# --------------------------------------------------

hourly = hourly.dropna()


# --------------------------------------------------
# SAVE PROCESSED DATA
# --------------------------------------------------

output_path = PROCESSED_DIR / "hourly_energy.csv"

hourly.to_csv(output_path)

print("\n----------------------------------------")
print("PREPROCESSING COMPLETED")
print("----------------------------------------")
print(f"Processed rows: {len(hourly):,}")
print(f"Output file: {output_path}")
print("----------------------------------------")
print(hourly.head())