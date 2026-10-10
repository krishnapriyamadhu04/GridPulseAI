
from pathlib import Path
import json
import csv
import io
import re
import math
from datetime import date, datetime

import joblib
import pandas as pd
import pytesseract

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

from fastapi import (
    FastAPI,
    Request,
    HTTPException,
    UploadFile,
    File,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from PIL import Image, ImageOps, ImageEnhance

from backend.services.weather_service import get_weather
from backend.services.ai_service import generate_advice

from backend.auth import (
    initialize_database,
    create_user,
    authenticate_user,
    create_session,
    get_current_user,
    delete_session,
    require_user,
    get_security_question,
    reset_password,
)

from backend.energy_service import (
    initialize_energy_storage,
    save_reading,
    get_user_readings
)


# ==================================================
# AUTH REQUEST MODELS
# ==================================================

class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    security_question: str
    security_answer: str

class SecurityQuestionRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    security_answer: str
    new_password: str

class EnergyReadingRequest(BaseModel):
    reading_date: date
    consumption_kwh: float

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

MODEL_DIR = (
    PROJECT_ROOT
    / "ml"
    / "models"
)

FRONTEND_DIR = (
    PROJECT_ROOT
    / "frontend"
)


# ==================================================
# APP
# ==================================================

app = FastAPI(
    title="GridPulseAI",
    description=(
        "AI-Based Energy Consumption "
        "Forecasting & Optimization Agent"
    ),
    version="1.0.0"
)


# ==================================================
# DATABASE
# ==================================================

initialize_database()
initialize_energy_storage()



# ==================================================
# PERSONAL ENERGY READINGS & BILL UPLOAD
# ==================================================

MAX_BILL_SIZE = 10 * 1024 * 1024

ALLOWED_BILL_EXTENSIONS = {
    ".pdf", ".csv", ".jpg", ".jpeg", ".png"
}


@app.post("/api/energy/readings")
def create_energy_reading(
    data: EnergyReadingRequest,
    request: Request
):
    user = require_user(request)
    consumption = data.consumption_kwh

    if not math.isfinite(consumption) or consumption < 0:
        raise HTTPException(
            status_code=400,
            detail="Consumption must be a valid number of 0 or more."
        )

    save_reading(
        user_id=user["id"],
        reading_date=data.reading_date.isoformat(),
        consumption_kwh=consumption,
        source="manual"
    )

    return {"message": "Energy reading saved successfully."}

@app.get("/api/energy/personal-summary")
def personal_energy_summary(request: Request):
    user = require_user(request)

    readings = get_user_readings(user["id"])

    if not readings:
        return {
            "has_data": False,
            "message": "Save your first electricity reading to begin."
        }

    df = pd.DataFrame(readings)
    df["reading_date"] = pd.to_datetime(
        df["reading_date"], errors="coerce"
    )
    df["consumption_kwh"] = pd.to_numeric(
        df["consumption_kwh"], errors="coerce"
    )

    df = df.dropna(
        subset=["reading_date", "consumption_kwh"]
    )
    df = df[
        df["consumption_kwh"].ge(0)
    ].sort_values("reading_date")

    if df.empty:
        return {
            "has_data": False,
            "message": "No valid readings were found."
        }

    # Group multiple readings in the same calendar month.
    monthly = (
        df.assign(
            month=df["reading_date"].dt.to_period("M")
        )
        .groupby("month")["consumption_kwh"]
        .sum()
        .sort_index()
    )

    average = float(monthly.mean())
    latest = float(monthly.iloc[-1])

    # A baseline estimate, not a trained ML forecast.
    # With only one month, use the latest month's consumption.
    estimate = latest

    if len(monthly) >= 3:
        recent = monthly.tail(3)
        changes = recent.diff().dropna()
        average_change = float(changes.mean())

        # Limit trend extrapolation to avoid extreme estimates
        # from a short or irregular history.
        max_change = max(average * 0.25, 1.0)
        average_change = max(
            -max_change,
            min(average_change, max_change)
        )
        estimate = max(0.0, latest + average_change)

    return {
        "has_data": True,
        "reading_count": int(len(df)),
        "months_available": int(len(monthly)),
        "latest_reading_date": (
            df.iloc[-1]["reading_date"].date().isoformat()
        ),
        "latest_month_kwh": round(latest, 2),
        "average_monthly_kwh": round(average, 2),
        "estimated_next_month_kwh": round(estimate, 2),
        "forecast_type": "historical_baseline",
        "forecast_note": (
            "This is a baseline estimate based on your saved monthly "
            "readings. It is not yet a weather-trained ML prediction."
        ),
        "monthly_history": [
            {
                "month": str(month),
                "consumption_kwh": round(float(value), 2)
            }
            for month, value in monthly.items()
        ]
    }

@app.get("/api/energy/readings")
def read_energy_readings(request: Request):
    user = require_user(request)

    return {
        "readings": get_user_readings(user["id"])
    }


def extract_bill_image(content: bytes) -> dict:
    """Extract possible date and consumption values from an electricity bill."""

    try:
        image = Image.open(io.BytesIO(content))
        image = ImageOps.exif_transpose(image).convert("L")

        # Enlarge the image to improve OCR accuracy.
        if image.width < 1800:
            scale = 1800 / image.width
            image = image.resize(
                (1800, int(image.height * scale))
            )

        image = ImageEnhance.Contrast(image).enhance(2)

        # Try more than one OCR layout.
        text_blocks = []

        for psm in (6, 11):
            result = pytesseract.image_to_string(
                image,
                config=f"--oem 3 --psm {psm}"
            )
            if result.strip():
                text_blocks.append(result)

        text = "\n".join(text_blocks)

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not process the bill image. "
                "Check the image file and Tesseract installation."
            )
        ) from exc

    # Normalize common OCR errors without changing the original text.
    normalized = text.replace("\u00a0", " ")

    # Accept common date formats:
    # YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    date_patterns = [
        r"\b(20\d{2}-\d{1,2}-\d{1,2})\b",
        r"\b(\d{1,2}[/-]\d{1,2}[/-]20\d{2})\b",
        r"\b(\d{1,2}\.\d{1,2}\.20\d{2})\b",
    ]

    def parse_bill_date(value):
        formats = (
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d.%m.%Y",
        )

        for fmt in formats:
            try:
                return datetime.strptime(
                    value, fmt
                ).date().isoformat()
            except ValueError:
                continue

        return None

    # Prefer dates close to a billing/reading label.
    date_value = None
    date_label = re.compile(
        r"(?:bill date|reading date|meter reading date|"
        r"billing date|present reading date|date of reading)",
        re.IGNORECASE
    )

    lines = normalized.splitlines()

    for index, line in enumerate(lines):
        if date_label.search(line):
            nearby = " ".join(
                lines[index:index + 2]
            )

            for pattern in date_patterns:
                match = re.search(
                    pattern, nearby
                )
                if match:
                    date_value = parse_bill_date(
                        match.group(1)
                    )
                    if date_value:
                        break

        if date_value:
            break

    # Fallback: first valid date found.
    if not date_value:
        for pattern in date_patterns:
            for match in re.finditer(pattern, normalized):
                date_value = parse_bill_date(
                    match.group(1)
                )
                if date_value:
                    break
            if date_value:
                break

    # Look for consumption explicitly labelled in the bill.
    # Avoid treating bill amount, meter number, or tariff as units.
    consumption_patterns = [
        r"(?:energy\s+consumed|consumption|"
        r"units\s+consumed|consumed\s+units|"
        r"consumption\s+units|total\s+units)"
        r"\s*[:=\-]?\s*([0-9,]+(?:\.\d+)?)"
        r"\s*(?:kwh|units?)?\b",

        r"\b(?:kwh\s+consumed|units)"
        r"\s*[:=\-]?\s*([0-9,]+(?:\.\d+)?)"
        r"\s*(?:kwh)?\b",
    ]

    consumption_value = None

    for pattern in consumption_patterns:
        match = re.search(
            pattern,
            normalized,
            re.IGNORECASE
        )

        if match:
            try:
                candidate = float(
                    match.group(1).replace(",", "")
                )

                if math.isfinite(candidate) and candidate >= 0:
                    consumption_value = candidate
                    break

            except ValueError:
                continue

    complete = (
        date_value is not None
        and consumption_value is not None
    )

    return {
        "reading_date": date_value,
        "consumption_kwh": consumption_value,
        "message": (
            "Please verify the extracted values before saving."
            if complete
            else
            "The bill could not be read completely. "
            "Please check the date and consumption manually."
        ),
    }



@app.post("/api/energy/upload")
async def upload_energy_bill(
    request: Request,
    bill: UploadFile = File(...)
):
    require_user(request)

    filename = bill.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_BILL_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Upload a PDF, CSV, JPG or PNG bill."
        )

    content = await bill.read(MAX_BILL_SIZE + 1)
    await bill.close()

    if len(content) > MAX_BILL_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The bill must be smaller than 10 MB."
        )

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    # Image OCR
    if extension in {".jpg", ".jpeg", ".png"}:
        return extract_bill_image(content)

    # CSV: requires reading_date and consumption_kwh columns.
    if extension == ".csv":
        try:
            decoded = content.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(decoded))

            headers = {
                (name or "").strip().lower()
                for name in (reader.fieldnames or [])
            }

            if not {"reading_date", "consumption_kwh"}.issubset(headers):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "CSV must contain reading_date and "
                        "consumption_kwh columns."
                    )
                )

            rows = list(reader)
            if not rows:
                raise HTTPException(
                    status_code=400,
                    detail="The CSV contains no readings."
                )

            row = {
                (key or "").strip().lower(): value
                for key, value in rows[-1].items()
            }

            reading_date = date.fromisoformat(
                row["reading_date"].strip()
            ).isoformat()

            consumption = float(row["consumption_kwh"].strip())

            if not math.isfinite(consumption) or consumption < 0:
                raise ValueError("Invalid consumption.")

            return {
                "reading_date": reading_date,
                "consumption_kwh": consumption,
                "message": (
                    "Review the extracted details, then save the reading."
                )
            }

        except HTTPException:
            raise
        except (UnicodeDecodeError, ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Could not read the CSV. Check the date format "
                    "(YYYY-MM-DD) and consumption value."
                )
            )

    # PDF: extracts selectable text. Scanned PDFs need OCR separately.
    if extension == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            text_content = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Install PDF support: python -m pip install pypdf"
            )
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Could not open this PDF bill."
            )

        if not text_content.strip():
            return {
                "reading_date": None,
                "consumption_kwh": None,
                "message": (
                    "No selectable text was found. Try a JPG/PNG image "
                    "or enter the values manually."
                )
            }

        date_match = re.search(
            r"\b(20\d{2}-\d{2}-\d{2})\b",
            text_content
        )

        kwh_match = re.search(
            r"(?:energy consumed|consumption|units consumed|units)"
            r"\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*kwh\b",
            text_content,
            re.IGNORECASE
        )

        if date_match and kwh_match:
            try:
                reading_date = date.fromisoformat(
                    date_match.group(1)
                ).isoformat()

                consumption = float(kwh_match.group(1))

                if math.isfinite(consumption) and consumption >= 0:
                    return {
                        "reading_date": reading_date,
                        "consumption_kwh": consumption,
                        "message": (
                            "Review the extracted details, then save the reading."
                        )
                    }
            except ValueError:
                pass

    return {
        "reading_date": None,
        "consumption_kwh": None,
        "message": (
            "The date or consumption could not be extracted reliably. "
            "Check the bill and enter the details manually."
        )
    }



# ==================================================
# CORS
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# LOAD DATA
# ==================================================

def load_data():

    if not DATA_PATH.exists():

        raise FileNotFoundError(
            "Processed dataset not found. "
            "Run python ml/preprocess.py first."
        )

    return pd.read_csv(
        DATA_PATH,
        index_col=0,
        parse_dates=True
    ).sort_index()


# ==================================================
# PUBLIC HEALTH CHECK
# ==================================================

@app.get("/api/health")
def health():

    return {
        "status": "online",
        "project": "GridPulseAI"
    }


# ==================================================
# AUTHENTICATION
# ==================================================

@app.post("/api/auth/signup")
def signup(data: SignupRequest):

    if len(data.name.strip()) < 2:

        raise HTTPException(
            status_code=400,
            detail="Please enter your name."
        )

    if len(data.password) < 6:

        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 6 characters."
        )

    try:

        user_id = create_user(
            name=data.name, 
            email=data.email, 
            password=data.password, 
            security_question=data.security_question, 
            security_answer=data.security_answer 
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    return {
        "message": "Account created successfully.",
        "user_id": user_id
    }


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.post("/api/auth/login")
def login(data: LoginRequest):

    user = authenticate_user(
        email=data.email.strip(),
        password=data.password
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )

    session_token = create_session(
        user["id"]
    )

    response = JSONResponse(
        content={
            "message": "Login successful.",
            "user": {
                "name": user["name"],
                "email": user["email"]
            }
        }
    )

    response.set_cookie(
    key="gridpulse_session",
    value=session_token,
    httponly=True,
    samesite="lax",
    secure=False,
    path="/"
)

    return response


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.post("/api/auth/logout")
def logout(request: Request):

    token = request.cookies.get(
        "gridpulse_session"
    )

    if token:
        delete_session(token)

    response = JSONResponse(
        content={
            "message": "Logged out successfully."
        }
    )

    response.delete_cookie(
        key="gridpulse_session"
    )

    return response

# ==========================================
# FORGOT PASSWORD - GET SECURITY QUESTION
# ==========================================

@app.post("/api/auth/security-question")
def security_question(data: SecurityQuestionRequest):
    question = get_security_question(data.email)

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Account not found or security question not set."
        )

    return {"security_question": question}


# ==========================================
# FORGOT PASSWORD - RESET PASSWORD
# ==========================================

@app.post("/api/auth/forgot-password")
def forgot_password(data: ResetPasswordRequest):

    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long."
        )

    success = reset_password(
        email=data.email,
        security_answer=data.security_answer,
        new_password=data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Invalid email or security answer."
        )

    return {
        "message": "Password reset successfully. Please log in again."
    }


# ==================================================
# FRONTEND AUTH PAGES
# ==================================================


@app.get("/")
def home(request: Request):
    # Opening the app's home URL starts a fresh login flow.
    token = request.cookies.get("gridpulse_session")

    if token:
        delete_session(token)

    response = RedirectResponse(
        url="/login",
        status_code=303
    )

    response.delete_cookie(
        key="gridpulse_session",
        path="/"
    )

    return response



@app.get("/login")
def login_page():

    return FileResponse(
        FRONTEND_DIR / "login.html"
    )


@app.get("/signup")
def signup_page():

    return FileResponse(
        FRONTEND_DIR / "signup.html"
    )

@app.get("/forgot-password")
def forgot_password_page():
    return FileResponse(
        FRONTEND_DIR / "forgot-password.html"
    )

@app.get("/dashboard")
def dashboard_page(request: Request):

    user = get_current_user(request)

    if not user:

        return RedirectResponse(
            url="/login",
            status_code=303
        )

    return FileResponse(
        FRONTEND_DIR / "index.html"
    )


# ==================================================
# DASHBOARD API
# ==================================================

@app.get("/api/dashboard")
def dashboard(request: Request):

    require_user(request)

    df = load_data()

    latest = float(
        df["energy_kwh"].iloc[-1]
    )

    average_24h = float(
        df["energy_kwh"].tail(24).mean()
    )

    return {
        "latest_consumption_kwh": latest,
        "average_24h_kwh": average_24h,
        "timestamp": str(df.index[-1])
    }


# ==================================================
# CONSUMPTION HISTORY
# ==================================================

@app.get("/api/consumption")
def consumption(
    request: Request,
    hours: int = 168
):

    require_user(request)

    df = load_data()

    data = df.tail(hours)

    return {
        "timestamps": [
            str(x)
            for x in data.index
        ],
        "values": [
            round(float(x), 4)
            for x in data["energy_kwh"]
        ]
    }


# ==================================================
# LSTM FORECAST
# ==================================================

@app.get("/api/forecast")
def forecast(request: Request):

    require_user(request)

    model_path = MODEL_DIR / "lstm.keras"
    scaler_path = MODEL_DIR / "lstm_scaler.joblib"

    if not model_path.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "LSTM model not found. "
                "Run python ml/train_models.py"
            )
        )

    from tensorflow.keras.models import load_model

    df = load_data()

    model = load_model(
        model_path
    )

    scaler = joblib.load(
        scaler_path
    )

    latest_values = (
        df["energy_kwh"]
        .tail(24)
        .values
        .reshape(-1, 1)
    )

    scaled = scaler.transform(
        latest_values
    )

    sequence = scaled.reshape(
        1,
        24,
        1
    )

    prediction_scaled = model.predict(
        sequence,
        verbose=0
    )

    prediction = scaler.inverse_transform(
        prediction_scaled
    )[0][0]

    return {
        "forecast_kwh": round(
            float(prediction),
            4
        ),
        "forecast_for": "next_hour"
    }


# ==================================================
# MODEL RESULTS
# ==================================================

@app.get("/api/models")
def models(request: Request):

    require_user(request)

    path = MODEL_DIR / "model_results.json"

    if not path.exists():

        raise HTTPException(
            status_code=404,
            detail="Model results not found."
        )

    with open(path, "r") as file:

        return json.load(file)


# ==================================================
# ANOMALY
# ==================================================

@app.get("/api/anomalies")
def anomalies(request: Request):

    require_user(request)

    path = MODEL_DIR / "anomalies.csv"

    if not path.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "Anomaly model has not been trained."
            )
        )

    df = pd.read_csv(
        path,
        index_col=0,
        parse_dates=True
    )

    latest = df.iloc[-1]

    return {
        "anomaly": bool(
            latest["anomaly"]
        ),
        "anomaly_score": round(
            float(latest["anomaly_score"]),
            4
        ),
        "timestamp": str(
            df.index[-1]
        )
    }


# ==================================================
# WEATHER
# ==================================================

@app.get("/api/weather")
def weather(
    request: Request,
    location: str
):

    require_user(request)

    if not location.strip():

        raise HTTPException(
            status_code=400,
            detail="Please enter a location."
        )

    try:

        return get_weather(
            location.strip()
        )

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )



# ==================================================
# AI ADVISOR — AVAILABLE WITHOUT PERSONAL HISTORY
# ==================================================

@app.get("/api/advisor")
def advisor(
    request: Request,
    question: str = ""
):
    user = require_user(request)

    question = question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Please enter an energy-related question."
        )

    readings = get_user_readings(user["id"])

    if readings:
        df = pd.DataFrame(readings)
        df["consumption_kwh"] = pd.to_numeric(
            df["consumption_kwh"], errors="coerce"
        )
        values = (
            df["consumption_kwh"]
            .dropna()
            .loc[lambda series: series >= 0]
        )

        recent_average = (
            float(values.tail(3).mean())
            if not values.empty
            else 0.0
        )

        forecast_value = (
            float(values.iloc[-1])
            if not values.empty
            else 0.0
        )
    else:
        recent_average = 0.0
        forecast_value = 0.0

    try:
        advice = generate_advice(
            forecast=forecast_value,
            recent_average=recent_average,
            anomaly=False,
            question=question
        )
    except Exception as exc:
        # Keep the endpoint available if the advice service fails.
        raise HTTPException(
            status_code=503,
            detail="The AI advice service is currently unavailable."
        ) from exc

    return {
        "advice": advice,
        "has_personal_readings": bool(readings),
        "message": (
            "Advice uses your saved readings."
            if readings
            else "General energy advice; save readings for personalized analysis."
        )
    }




# ==================================================
# STATIC FRONTEND FILES
# ==================================================

app.mount(
    "/static",
    StaticFiles(
        directory=FRONTEND_DIR
    ),
    name="static"
)