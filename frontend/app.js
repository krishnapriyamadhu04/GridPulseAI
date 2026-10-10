/* =========================================================
   GridPulseAI — Complete Frontend JavaScript
   ========================================================= */


/* ---------- 1. Global variables ---------- */

let latestDashboardData = null;
let latestWeatherData = null;
let weatherClockInterval = null;

const API_BASE = "";


/* ---------- 2. General helper functions ---------- */

/**
 * Fetch JSON from the backend.
 * Displays useful errors for failed requests.
 */
async function fetchJSON(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            ...(options.headers || {})
        }
    });

    const contentType = response.headers.get("content-type") || "";

    let data;

    if (contentType.includes("application/json")) {
        data = await response.json();
    } else {
        const text = await response.text();
        data = { detail: text };
    }

    if (!response.ok) {
        const message =
            data.detail ||
            data.message ||
            data.error ||
            `Request failed with status ${response.status}`;

        throw new Error(
            typeof message === "string"
                ? message
                : JSON.stringify(message)
        );
    }

    return data;
}


function displayPersonalHistory(history) {
    const container = document.getElementById("personalHistory");

    if (!container) return;

    container.replaceChildren();

    if (!Array.isArray(history) || history.length === 0) {
        container.textContent = "Your monthly history will appear here.";
        return;
    }

    const heading = document.createElement("h3");
    heading.textContent = "Your Monthly Consumption";
    container.appendChild(heading);

    const list = document.createElement("ul");

    history.forEach(item => {
        const row = document.createElement("li");
        row.textContent =
            `${item.month}: ${formatNumber(item.consumption_kwh)} kWh`;
        list.appendChild(row);
    });

    container.appendChild(list);
}

/**
 * Return the first defined value from a list of possible keys.
 */
function getValue(object, keys, fallback = null) {
    if (!object || typeof object !== "object") {
        return fallback;
    }

    for (const key of keys) {
        if (
            Object.prototype.hasOwnProperty.call(object, key) &&
            object[key] !== null &&
            object[key] !== undefined
        ) {
            return object[key];
        }
    }

    return fallback;
}


/**
 * Convert a number-like value to a readable string.
 */
function formatNumber(value, decimals = 2) {
    if (value === null || value === undefined || value === "") {
        return "--";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return String(value);
    }

    return number.toLocaleString(undefined, {
        maximumFractionDigits: decimals,
        minimumFractionDigits: 0
    });
}


/**
 * Set text safely without interpreting HTML.
 */
function setText(id, value, fallback = "--") {
    const element = document.getElementById(id);

    if (!element) {
        return;
    }

    element.textContent =
        value === null || value === undefined || value === ""
            ? fallback
            : String(value);
}


/**
 * Show a message in the advisor result area.
 */
function showAdvisorMessage(message, type = "") {
    const result = document.getElementById("advisorResult");

    if (!result) return;

    const scrollY = window.scrollY;

    result.textContent = message;
    result.style.display = "block";
    result.className = "advisor-result";

    if (type) {
        result.classList.add(type);
    }

    requestAnimationFrame(() => {
        window.scrollTo({
            top: scrollY,
            behavior: "instant"
        });
    });
}


/**
 * Show an error in the browser console and optionally in a UI field.
 */
function logError(context, error) {
    console.error(`[GridPulseAI] ${context}:`, error);
}

function showDashboardContent(visible) {
    const dashboardContent = document.getElementById("dashboardContent");

    if (dashboardContent) {
        dashboardContent.style.display = visible ? "block" : "none";
    }
}



/* ---------- 3. Personal dashboard metrics ---------- */

async function loadDashboard() {
    return loadPersonalSummary();
}


function resetPersonalMetrics() {
    setText("latestConsumption", "0");
    setText("averageConsumption", "0");
    setText("forecast", "0");
    setConsumptionStatus("No readings yet", "status-warning");

    displayPersonalHistory([]);

    const forecastElement = document.getElementById("forecast");
    if (forecastElement) {
        forecastElement.title = "Add your energy readings to calculate an estimate.";
    }
}


async function loadPersonalSummary() {
    resetPersonalMetrics();
    try {
        const data = await fetchJSON(
            `${API_BASE}/api/energy/personal-summary`
        );

        const history = Array.isArray(data.monthly_history)
            ? data.monthly_history
            : [];

        // Remove the historical-baseline explanation bar.
        const note = document.getElementById("forecastNote");
        if (note) {
            note.style.display = "none";
            note.textContent = "";
        }

        displayPersonalHistory(history);

        if (!data.has_data || history.length === 0) {
            setText("latestConsumption", "0");
            setText("averageConsumption", "0");
            setText("forecast", "0");
            setConsumptionStatus("No readings yet", "status-warning");

            showAdvisorMessage(
                "Your AI Energy Advisor is ready! Ask about electricity bills, " +
                "appliances, energy-saving tips, or ways to reduce your bill."
            );

            enableAdvisor();
            return data;
        }

        const latest = Number(data.latest_month_kwh);
        const average = Number(data.average_monthly_kwh);

        setText("latestConsumption", formatNumber(latest));
        setText("averageConsumption", formatNumber(average));

        // Compare the latest month's consumption with previous months.
        const previousMonths = history
            .slice(0, -1)
            .map(item => Number(item.consumption_kwh))
            .filter(value => Number.isFinite(value) && value >= 0);

        let status = "Normal";
        let statusClass = "status-normal";

        if (previousMonths.length === 0) {
            // A single month cannot establish a personal baseline.
            status = "Building baseline";
            statusClass = "status-warning";
        } else {
            const baseline = previousMonths.reduce(
                (sum, value) => sum + value, 0
            ) / previousMonths.length;

            if (baseline > 0) {
                if (latest > baseline * 1.20) {
                    status = "High";
                    statusClass = "status-danger";
                } else if (latest < baseline * 0.80) {
                    status = "Low";
                    statusClass = "status-normal";
                }
            } else if (latest > 0) {
                status = "High";
                statusClass = "status-danger";
            }
        }

        setConsumptionStatus(status, statusClass);

        // Show the available estimate without requiring three months.
        // The backend's estimate is a baseline, not a weather-trained ML forecast.
        if (
            Number.isFinite(Number(data.estimated_next_month_kwh)) &&
            data.estimated_next_month_kwh !== null
        ) {
            setText(
                "forecast",
                formatNumber(data.estimated_next_month_kwh)
            );
        } else {
            setText("forecast", "--");
        }

        const forecastElement = document.getElementById("forecast");
        if (forecastElement) {
            forecastElement.title =
                "Preliminary estimate based on your saved monthly readings.";
            forecastElement.classList.remove("forecast-pending");
        }

        // The AI advisor stays available regardless of history length.
        enableAdvisor();

        return data;

    } catch (error) {
        logError("Loading personal energy summary", error);

        setText("latestConsumption", "--");
setText("averageConsumption", "--");
setText("forecast", "--");
setConsumptionStatus("Unavailable", "status-warning");
displayPersonalHistory([]);

        const note = document.getElementById("forecastNote");
        if (note) note.style.display = "none";

        // The advisor can still answer general energy questions.
        enableAdvisor();

        return null;
    }
}

function setConsumptionStatus(label, className) {
    const element = document.getElementById("anomaly");

    if (!element) return;

    element.textContent = label;
    element.classList.remove(
        "status-normal",
        "status-warning",
        "status-danger"
    );

    element.classList.add(className);
}

function enableAdvisor() {
    const input = document.getElementById("questionInput");
    const button = document.querySelector(".question-row button");

    if (input) input.disabled = false;
    if (button) button.disabled = false;
}



/* ---------- 4. Forecast ---------- */

/**
 * Load the next-hour prediction.
 *
 * Expected route:
 * GET /api/forecast
 */
async function loadForecast() {
    try {
        const data = await fetchJSON(`${API_BASE}/api/forecast`);

        const source =
            data.forecast ||
            data.prediction ||
            data.result ||
            data;

        const value = getValue(source, [
            "forecast",
            "prediction",
            "predicted_consumption",
            "predicted_value",
            "next_hour",
            "next_hour_forecast",
            "forecast_kwh",
            "predicted_kwh",
            "value"
        ]);

        const unit = getValue(source, [
            "unit",
            "units"
        ], "kWh");

        if (value !== null && typeof value === "object") {
            const nestedValue = getValue(value, [
                "value",
                "prediction",
                "forecast",
                "predicted_consumption"
            ]);

            setText(
                "forecast",
                nestedValue === null
                    ? JSON.stringify(value)
                    : formatNumber(nestedValue)
            );
        } else {
            setText(
                "forecast",
                value === null ? "--" : formatNumber(value)
            );
        }

        const forecastElement = document.getElementById("forecast");

        if (forecastElement && unit && unit !== "kWh") {
            forecastElement.title = `Unit: ${unit}`;
        }

        return data;
    } catch (error) {
        logError("Loading forecast", error);
        setText("forecast", "--");
        return null;
    }
}


/* ---------- 5. Anomaly detection ---------- */

/**
 * Load anomaly detection result.
 *
 * Expected route:
 * GET /api/anomalies
 */
async function loadAnomaly() {
    try {
        const data = await fetchJSON(`${API_BASE}/api/anomalies`);

        const source =
            data.anomaly ||
            data.result ||
            data.status_data ||
            data;

        let status = getValue(source, [
            "status",
            "anomaly_status",
            "result",
            "label",
            "prediction",
            "is_anomaly",
            "anomaly"
        ]);

        if (status === null) {
            status = "Unavailable";
        }

        if (typeof status === "boolean") {
            status = status ? "Anomaly Detected" : "Normal";
        }

        if (typeof status === "number") {
            status = status === 1
                ? "Anomaly Detected"
                : "Normal";
        }

        const element = document.getElementById("anomaly");

        if (!element) {
            return data;
        }

        element.textContent = String(status);
        element.classList.remove(
            "status-normal",
            "status-warning",
            "status-danger"
        );

        const normalized = String(status).toLowerCase();

        if (
            normalized.includes("normal") ||
            normalized.includes("no anomaly") ||
            normalized.includes("safe")
        ) {
            element.classList.add("status-normal");
        } else if (
            normalized.includes("anomaly") ||
            normalized.includes("high") ||
            normalized.includes("abnormal") ||
            normalized.includes("alert")
        ) {
            element.classList.add("status-danger");
        } else {
            element.classList.add("status-warning");
        }

        return data;
    } catch (error) {
        logError("Loading anomaly status", error);
        setText("anomaly", "Unavailable");
        return null;
    }
}


/* ---------- 7. Weather descriptions and icons ---------- */

/**
 * Translate Open-Meteo weather codes to readable conditions.
 */
function getWeatherDescription(code) {
    const descriptions = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snowfall",
        73: "Moderate snowfall",
        75: "Heavy snowfall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    };

    return descriptions[Number(code)] || "Weather conditions unavailable";
}


/**
 * Return a suitable weather emoji for Open-Meteo weather codes.
 */
function getWeatherIcon(code, isDay = true) {
    code = Number(code);

    if (code === 0) {
        return isDay ? "☀️" : "🌙";
    }

    if (code === 1) {
        return isDay ? "🌤️" : "🌙";
    }

    if (code === 2) {
        return "⛅";
    }

    if (code === 3) {
        return "☁️";
    }

    if ([45, 48].includes(code)) {
        return "🌫️";
    }

    if ([51, 53, 55, 56, 57].includes(code)) {
        return "🌦️";
    }

    if ([61, 63, 65, 66, 67, 80, 81, 82].includes(code)) {
        return "🌧️";
    }

    if ([71, 73, 75, 77, 85, 86].includes(code)) {
        return "🌨️";
    }

    if ([95, 96, 99].includes(code)) {
        return "⛈️";
    }

    return "🌡️";
}


/* ---------- 8. Air quality helpers ---------- */

/**
 * Convert US AQI to a readable category.
 */
function getAQICategory(aqi) {
    const value = Number(aqi);

    if (!Number.isFinite(value)) {
        return "Unavailable";
    }

    if (value <= 50) {
        return "Good";
    }

    if (value <= 100) {
        return "Moderate";
    }

    if (value <= 150) {
        return "Unhealthy for sensitive groups";
    }

    if (value <= 200) {
        return "Unhealthy";
    }

    if (value <= 300) {
        return "Very unhealthy";
    }

    return "Hazardous";
}


/**
 * Calculate approximate heat index in Celsius.
 *
 * This uses a simplified formula and should be treated as an estimate.
 */
function calculateHeatIndex(temperature, humidity) {
    const t = Number(temperature);
    const rh = Number(humidity);

    if (
        !Number.isFinite(t) ||
        !Number.isFinite(rh)
    ) {
        return null;
    }

    // Heat index is generally meaningful at warmer temperatures.
    if (t < 27 || rh < 40) {
        return t;
    }

    const fahrenheit = (t * 9 / 5) + 32;

    const hiF =
        -42.379 +
        2.04901523 * fahrenheit +
        10.14333127 * rh -
        0.22475541 * fahrenheit * rh -
        0.00683783 * fahrenheit * fahrenheit -
        0.05481717 * rh * rh +
        0.00122874 * fahrenheit * fahrenheit * rh +
        0.00085282 * fahrenheit * rh * rh -
        0.00000199 * fahrenheit * fahrenheit * rh * rh;

    const hiC = (hiF - 32) * 5 / 9;

    if (!Number.isFinite(hiC)) {
        return t;
    }

    return Math.max(t, hiC);
}


/* ---------- 9. Weather clock ---------- */

/**
 * Update the displayed local time for the selected weather location.
 */
function updateWeatherTime() {
    const timeElement = document.getElementById("weatherTime");

    if (!timeElement || !latestWeatherData) {
        return;
    }

    const timezone = getValue(latestWeatherData, [
        "timezone",
        "time_zone"
    ]);

    const rawTime = getValue(latestWeatherData, [
        "time",
        "local_time",
        "timestamp"
    ]);

    if (timezone) {
        try {
            const timeText = new Intl.DateTimeFormat("en-IN", {
                timeZone: timezone,
                hour: "2-digit",
                minute: "2-digit",
                hour12: true
            }).format(new Date());

            const dateText = new Intl.DateTimeFormat("en-IN", {
                timeZone: timezone,
                day: "numeric",
                month: "short"
            }).format(new Date());

            timeElement.textContent = `${dateText} · ${timeText}`;
            return;
        } catch (error) {
            logError("Formatting weather location time", error);
        }
    }

    if (rawTime) {
        timeElement.textContent = String(rawTime);
    } else {
        timeElement.textContent = "";
    }
}


/* ---------- 10. Weather display ---------- */

/**
 * Update the weather panel from the backend response.
 */
function displayWeather(data) {
    latestWeatherData = data;

    const source =
        data.weather ||
        data.current ||
        data;

    const location = getValue(data, [
        "location",
        "name",
        "city"
    ], "Selected location");

    const admin = getValue(data, [
        "admin1",
        "region",
        "state"
    ]);

    const country = getValue(data, [
        "country"
    ]);

    const locationParts = [
        location,
        admin,
        country
    ].filter(Boolean);

    setText(
        "weatherLocation",
        [...new Set(locationParts)].join(", "),
        "Selected location"
    );

    const temperature = getValue(source, [
        "temperature",
        "temperature_2m",
        "temp",
        "temperature_c"
    ]);

    const apparentTemperature = getValue(source, [
        "apparent_temperature",
        "apparentTemperature",
        "feels_like",
        "feelsLike"
    ]);

    const humidity = getValue(source, [
        "humidity",
        "relative_humidity_2m",
        "relative_humidity"
    ]);

    const windSpeed = getValue(source, [
        "wind_speed",
        "wind_speed_10m",
        "windspeed"
    ]);

    const windGusts = getValue(source, [
        "wind_gusts",
        "wind_gusts_10m",
        "windgusts"
    ]);

    const weatherCode = getValue(source, [
        "weather_code",
        "weathercode",
        "code"
    ]);

    const isDayValue = getValue(source, [
        "is_day",
        "isDay"
    ], 1);

    const isDay = (
        isDayValue === true ||
        Number(isDayValue) === 1
    );

    const aqi = getValue(source, [
        "us_aqi",
        "aqi",
        "air_quality_index"
    ]);

    const pm25 = getValue(source, [
        "pm2_5",
        "pm25",
        "pm2_5_concentration"
    ]);

    const pm10 = getValue(source, [
        "pm10",
        "pm10_concentration"
    ]);

    const ozone = getValue(source, [
        "ozone",
        "o3"
    ]);

    setText(
        "temperature",
        temperature === null ? "--" : formatNumber(temperature, 1)
    );

    setText(
        "apparentTemperature",
        apparentTemperature === null
            ? "--"
            : `${formatNumber(apparentTemperature, 1)}°C`
    );

    setText(
        "humidity",
        humidity === null ? "--" : `${formatNumber(humidity, 0)}%`
    );

    setText(
        "wind",
        windSpeed === null
            ? "--"
            : `${formatNumber(windSpeed, 1)} km/h`
    );

    setText(
        "windGusts",
        windGusts === null
            ? "--"
            : `${formatNumber(windGusts, 1)} km/h`
    );

    setText(
        "pm25",
        pm25 === null ? "--" : `${formatNumber(pm25, 1)} µg/m³`
    );

    setText(
        "pm10",
        pm10 === null ? "--" : `${formatNumber(pm10, 1)} µg/m³`
    );

    setText(
        "ozone",
        ozone === null ? "--" : `${formatNumber(ozone, 1)} µg/m³`
    );

    if (aqi === null) {
        setText("airQuality", "Unavailable");
    } else {
        setText(
            "airQuality",
            `${getAQICategory(aqi)} (${formatNumber(aqi, 0)})`
        );
    }

    const heatIndex = calculateHeatIndex(temperature, humidity);

    setText(
        "heatIndex",
        heatIndex === null
            ? "--"
            : `${formatNumber(heatIndex, 1)}°C`
    );

    setText(
        "weatherCondition",
        weatherCode === null
            ? "Weather conditions unavailable"
            : getWeatherDescription(weatherCode)
    );

    const iconElement = document.getElementById("weatherIcon");

    if (iconElement) {
        iconElement.textContent =
            weatherCode === null
                ? "🌡️"
                : getWeatherIcon(weatherCode, isDay);
    }

    const emptyState = document.getElementById("weatherEmpty");
    const content = document.getElementById("weatherContent");

    if (emptyState) {
        emptyState.style.display = "none";
    }

    if (content) {
        content.style.display = "grid";
    }

    updateWeatherTime();

    if (weatherClockInterval) {
        clearInterval(weatherClockInterval);
    }

    weatherClockInterval = setInterval(updateWeatherTime, 60000);
}


/* ---------- 11. Load weather ---------- */

/**
 * Load weather for the location typed by the user.
 *
 * Expected route:
 * GET /api/weather?location=City
 */
async function loadWeather() {
    const input = document.getElementById("locationInput");
    const button = document.getElementById("weatherSearchBtn");
    const status = document.getElementById("weatherStatus");

    if (!input || !status) {
        return;
    }

    const location = input.value.trim();

    if (!location) {
        status.className = "error";
        status.textContent = "Please enter a city or location.";
        status.style.display = "block";
        input.focus();
        return;
    }

    showDashboardContent(false);

    status.className = "loading";
    status.textContent = "Fetching weather conditions...";
    status.style.display = "flex";

    if (button) {
        button.disabled = true;
        button.textContent = "Loading...";
    }

    try {
        const url =
            `${API_BASE}/api/weather?location=${encodeURIComponent(location)}`;

        const data = await fetchJSON(url);

        if (
            data &&
            (
                data.error ||
                data.success === false
            )
        ) {
            throw new Error(
                data.message ||
                data.error ||
                "Unable to load weather for this location."
            );
        }

        
displayWeather(data);

// Show the dashboard after weather loads successfully.
showDashboardContent(true);

        status.className = "";
        status.textContent = "";
        status.style.display = "none";
    } catch (error) {
        logError("Loading weather", error);

        status.className = "error";
        status.textContent =
            error.message ||
            "Unable to load weather. Please try another location.";

        status.style.display = "block";
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Update Weather";
        }
    }
}


/* ---------- 12. More Details popup ---------- */

/**
 * Open or close the More Details popup.
 *
 * Pass false to force it closed.
 * Pass true to force it open.
 * Call without an argument to toggle it.
 */
function toggleWeatherDetails(forceState) {
    const details = document.getElementById("extraWeatherDetails");
    const button = document.getElementById("moreDetailsBtn");
    const arrow = document.getElementById("detailsArrow");

    if (!details || !button) {
        return;
    }

    const isCurrentlyOpen = details.style.display !== "none";

    const shouldOpen =
        typeof forceState === "boolean"
            ? forceState
            : !isCurrentlyOpen;

    details.style.display = shouldOpen ? "block" : "none";

    button.setAttribute(
        "aria-expanded",
        String(shouldOpen)
    );

    if (arrow) {
        arrow.textContent = shouldOpen ? "⌄" : "›";
    }
}


/**
 * Close the weather popup when clicking outside it.
 */
document.addEventListener("click", function (event) {
    const details = document.getElementById("extraWeatherDetails");
    const button = document.getElementById("moreDetailsBtn");

    if (!details || !button) {
        return;
    }

    if (details.style.display === "none") {
        return;
    }

    const wrapper = button.closest(".weather-details-wrapper");

    if (wrapper && !wrapper.contains(event.target)) {
        toggleWeatherDetails(false);
    }
});


/* ---------- 13. AI Energy Optimization Advisor ---------- */

/**
 * Send the user's question to the advisor backend.
 *
 * Expected route:
 * POST /api/advisor
 *
 * This sends both "question" and "prompt" so backends that accept
 * either common field name can read the question.
 */

/* ---------- AI Energy Optimization Advisor ---------- */

async function askAdvisor() {
    const input = document.getElementById("questionInput");

    if (!input) return;

    const question = input.value.trim();

    if (!question) {
        showAdvisorMessage(
            "Please enter a question about energy consumption.",
            "error"
        );
        input.focus();
        return;
    }

    const button = document.querySelector(".question-row button");

    if (button) {
        button.disabled = true;
        button.textContent = "Thinking...";
    }

    showAdvisorMessage("Preparing your energy advice...", "loading");

    try {
        const url =
            `${API_BASE}/api/advisor?question=${encodeURIComponent(question)}`;

        const data = await fetchJSON(url);

        

const answer = getValue(data, [
    "answer",
    "response",
    "recommendation",
    "advice",
    "result",
    "message"
]);

if (answer === null || answer === "") {
    showAdvisorMessage(
        "No answer was returned. Please try again.",
        "error"
    );
} else {
    showAdvisorMessage(
        typeof answer === "object"
            ? JSON.stringify(answer, null, 2)
            : String(answer)
    );
}



        showAdvisorMessage(
            answer === null
                ? "No advice was returned. Please try again."
                : typeof answer === "object"
                    ? JSON.stringify(answer, null, 2)
                    : String(answer)
        );

    } catch (error) {
        logError("AI advisor request", error);

        showAdvisorMessage(
            error.message ||
                "Unable to get advice. Please try again.",
            "error"
        );
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Ask AI";
        }
    }
}



/* ---------- Electricity bill upload and personal readings ---------- */

/**
 * Upload a bill for extraction.
 * Extracted values must be checked before saving.
 */
async function uploadElectricityBill(event) {
    event.preventDefault();

    const fileInput = document.getElementById("billFile");
    const status = document.getElementById("billUploadStatus");
    const button = document.getElementById("uploadBillBtn");
    const file = fileInput?.files?.[0];

    if (!file || !status) {
        return;
    }

    const allowedExtensions = ["pdf", "csv", "jpg", "jpeg", "png"];
    const extension = file.name.split(".").pop().toLowerCase();

    if (!allowedExtensions.includes(extension)) {
        status.textContent = "Please choose a PDF, CSV, JPG or PNG file.";
        return;
    }

    // Keep uploads reasonably small.
    if (file.size > 10 * 1024 * 1024) {
        status.textContent = "The bill must be smaller than 10 MB.";
        return;
    }

    const formData = new FormData();
    formData.append("bill", file);

    button.disabled = true;
    button.textContent = "Uploading...";
    status.textContent = "Uploading and checking your bill...";

    try {
        const data = await fetchJSON(
            `${API_BASE}/api/energy/upload`,
            {
                method: "POST",
                body: formData
            }
        );

        // The backend may return a candidate reading for verification.
        const readingDate = document.getElementById("readingDate");
        const consumption = document.getElementById("consumptionKwh");

        if (data.reading_date && readingDate) {
            readingDate.value = data.reading_date;
        }

        if (
            data.consumption_kwh !== null &&
            data.consumption_kwh !== undefined &&
            consumption
        ) {
            consumption.value = data.consumption_kwh;
        }

        if (
            data.reading_date &&
            data.consumption_kwh !== null &&
            data.consumption_kwh !== undefined
        ) {
            status.textContent =
                "Possible reading extracted. Verify the date and kWh below, then click Save Reading.";
        } else {
            status.textContent =
                data.message ||
                "The bill was uploaded, but its consumption could not be extracted reliably. Enter the values manually below.";
        }
    } catch (error) {
        logError("Electricity bill upload", error);
        status.textContent =
            error.message || "Unable to process this bill.";
    } finally {
        button.disabled = false;
        button.textContent = "Upload Bill";
    }
}


/**
 * Save a user-confirmed energy reading.
 */
async function saveManualReading(event) {
    event.preventDefault();

    const dateInput = document.getElementById("readingDate");
    const consumptionInput = document.getElementById("consumptionKwh");
    const status = document.getElementById("readingStatus");
    const button = document.getElementById("saveReadingBtn");

    if (!dateInput || !consumptionInput || !status || !button) {
        return;
    }

    const readingDate = dateInput.value;
    const consumption = Number(consumptionInput.value);

    if (!readingDate) {
        status.textContent = "Please select the reading date.";
        return;
    }

    if (
        consumptionInput.value.trim() === "" ||
        !Number.isFinite(consumption) ||
        consumption < 0
    ) {
        status.textContent =
            "Enter a valid consumption value of 0 kWh or more.";
        return;
    }

    button.disabled = true;
    button.textContent = "Saving...";
    status.textContent = "Saving your reading...";

    try {
        await fetchJSON(`${API_BASE}/api/energy/readings`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                reading_date: readingDate,
                consumption_kwh: consumption
            })
        });

        status.textContent = "Reading saved successfully.";

        consumptionInput.value = "";

        await loadPersonalSummary();
    } catch (error) {
        logError("Saving energy reading", error);
        status.textContent =
            error.message || "Unable to save this reading.";
    } finally {
        button.disabled = false;
        button.textContent = "Save Reading";
    }
}



/* ---------- 14. Logout ---------- */

async function logout() {
    try {
        await fetchJSON(`${API_BASE}/api/auth/logout`, {
            method: "POST"
        });
    } catch (error) {
        logError("Logging out", error);
    } finally {
        // Prevent the dashboard from reappearing from browser cache.
        window.location.replace("/login");
    }
}


/* ---------- 15. Dashboard initialization ---------- */

/**
 * Initialize the dashboard when the page loads.
 */

async function initializeDashboard() {
    const weatherContent = document.getElementById("weatherContent");
    const weatherEmpty = document.getElementById("weatherEmpty");
    const weatherStatus = document.getElementById("weatherStatus");

    // Show the energy dashboard independently of weather.
    showDashboardContent(true);

    // Start with an empty weather state.
    if (weatherContent) {
        weatherContent.style.display = "none";
    }

    if (weatherEmpty) {
        weatherEmpty.style.display = "flex";
    }

    if (weatherStatus) {
        weatherStatus.style.display = "none";
        weatherStatus.textContent = "";
        weatherStatus.className = "";
    }

    // The advisor works even when the user has no readings.
    enableAdvisor();

    // Hide the preliminary forecast explanation.
    const note = document.getElementById("forecastNote");
    if (note) {
        note.style.display = "none";
        note.textContent = "";
    }

    // Load this user's readings without waiting for weather.
    resetPersonalMetrics();
}



/* ---------- 16. Keyboard support ---------- */

// Press Enter in the location field to fetch weather.
document.addEventListener("DOMContentLoaded", function () {
    const locationInput = document.getElementById("locationInput");

    if (locationInput) {
        locationInput.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                loadWeather();
            }
        });
    }

    // Press Enter in the advisor field to send a question.
    const questionInput = document.getElementById("questionInput");

    if (questionInput) {
        questionInput.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                askAdvisor();
            }
        });
    }

    
    const billUploadForm = document.getElementById("billUploadForm");

    if (billUploadForm) {
        billUploadForm.addEventListener(
            "submit",
            uploadElectricityBill
        );
    }

    const manualReadingForm = document.getElementById("manualReadingForm");

    if (manualReadingForm) {
        manualReadingForm.addEventListener(
            "submit",
            saveManualReading
        );
    }


    initializeDashboard();
});