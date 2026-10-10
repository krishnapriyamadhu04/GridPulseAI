# ⚡ GridPulseAI
### AI-Based Energy Consumption Forecasting & Optimization Agent

GridPulseAI is an intelligent energy monitoring and optimization application designed to help users understand electricity consumption patterns, forecast energy usage, and discover practical ways to improve energy efficiency.

The application combines machine learning, weather information, anomaly detection, and personalized energy advice in one platform.

## ✨ Features

- **Energy Consumption Forecasting** — Estimate future electricity usage using historical consumption data and machine learning models.
- **Personal Energy Insights** — View monthly consumption history, average usage, and baseline forecasts based on saved readings.
- **Anomaly Detection** — Identify unusual energy consumption patterns using Isolation Forest.
- **AI Energy Advisor** — Get practical energy-saving recommendations and answers to energy-related questions.
- **Weather Integration** — Retrieve weather information to help understand environmental factors that may influence energy usage.
- **Electricity Bill Upload** — Upload supported electricity bills and extract potential reading details for review.
- **User Authentication** — Provide separate user accounts and personalized energy records.
- **Interactive Dashboard** — Explore energy statistics, forecasts, and recommendations in one interface.

## 🛠️ Technology Stack

| Component | Technologies |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| Machine Learning | LSTM, Random Forest, XGBoost |
| Anomaly Detection | Isolation Forest |
| Data Processing | Pandas, NumPy, Scikit-learn |
| Model Storage | Joblib, Keras |
| Database | SQLite |
| Bill Text Extraction | Tesseract OCR, pytesseract |
| Weather Data | Open-Meteo API |

## 🧠 Machine Learning

GridPulseAI incorporates multiple machine learning approaches for energy analysis:

- **LSTM:** Models sequential patterns in energy consumption data.
- **Random Forest:** Supports prediction using learned relationships in the dataset.
- **XGBoost:** Provides a gradient-boosting model for predictive analysis.
- **Isolation Forest:** Detects potentially unusual consumption patterns.

The application also uses historical monthly readings to calculate a baseline forecast for personal energy summaries. This baseline is distinct from a weather-trained machine learning prediction.

## 🏗️ Project Structure

```text
GridPulseAI/
├── backend/
│   ├── app.py
│   ├── auth.py
│   ├── energy_service.py
│   └── services/
│       ├── ai_service.py
│       └── weather_service.py
├── frontend/
│   ├── index.html
│   ├── login.html
│   ├── signup.html
│   ├── upload.html
│   ├── app.js
│   └── style.css
├── data/
│   └── processed/
├── ml/
│   ├── anomaly_detection.py
│   ├── preprocess.py
│   ├── train_models.py
│   └── models/
├── requirements.txt
├── .gitignore
└── README.md
```

Some large datasets and trained model files are excluded from GitHub because of file-size limits. The application may require these files locally or through a separate model-storage solution.

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or a compatible version for the project's dependencies
- Git
- pip
- Tesseract OCR if using the electricity bill extraction feature

### 1. Clone the repository

```bash
git clone https://github.com/krishnapriyamadhu04/GridPulseAI.git
cd GridPulseAI
```

### 2. Create a virtual environment

**Windows:**

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure required files

Ensure that the required datasets, trained machine learning models, and environment configuration are available before starting the application.

If using bill OCR, install Tesseract OCR and configure its executable path for your operating system.

### 5. Start the FastAPI server

From the project root, run:

```bash
uvicorn backend.app:app --reload
```

Open the API documentation at:

```text
http://127.0.0.1:8000/docs
```

Use the application's configured frontend route to access the dashboard and authentication pages.

## 🔐 Security & Data

- Keep passwords, API keys, and other secrets out of source control.
- Configure secure cookies and HTTPS appropriately for production.
- Use persistent storage for user records when deploying the application.
- Review uploaded files and extracted bill information before saving them.

## ☁️ Deployment

GridPulseAI can be prepared for deployment on a Python-compatible hosting platform such as Render.

Before deployment, configure the required model files, OCR dependencies, environment variables, frontend static-file serving, and persistent database storage.

## 🔮 Future Improvements

- Weather-aware energy forecasting
- More accurate personalized forecasting with additional historical readings
- Expanded energy-saving recommendations
- Model performance comparison and evaluation dashboards
- Improved bill extraction and validation
- Cloud-based model and data storage
- Enhanced mobile-responsive dashboard

## 🎯 Project Objective

GridPulseAI was developed to explore how machine learning, time-series analysis, anomaly detection, and web technologies can be combined to build a practical energy management application.

The project aims to make electricity usage easier to understand and help users make more informed energy-consumption decisions.

## 👩‍💻 Author

**Krishna Priya Madhu**

[GitHub Profile](https://github.com/krishnapriyamadhu04)

---

*GridPulseAI — Understand your energy. Optimize your consumption.*