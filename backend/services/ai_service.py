
def generate_advice(
    forecast,
    recent_average,
    anomaly,
    temperature=None,
    humidity=None,
    question=None
):
    messages = []
    q = (question or "").strip().lower()

    # ---------------------------------------------
    # ANSWER GENERAL ENERGY QUESTIONS
    # ---------------------------------------------

    if q:
        if any(word in q for word in [
            "hello", "hi", "hey", "good morning",
            "good afternoon", "good evening"
        ]):
            messages.append(
                "Hello! I'm your GridPulseAI Energy Advisor. "
                "Ask me about electricity usage, appliances, "
                "electricity bills, or ways to save energy."
            )

        elif any(word in q for word in [
            "reduce", "save", "lower", "decrease",
            "electricity bill", "save electricity"
        ]):
            messages.append(
                "To reduce your electricity bill, switch off "
                "unused appliances, use LED bulbs, choose "
                "energy-efficient appliances, and avoid leaving "
                "devices on standby. Use air conditioning efficiently "
                "and run washing machines with full loads when practical. "
                "Your actual savings depend on your usage and tariff."
            )

        elif any(word in q for word in [
            "appliance", "consume the most", "uses the most",
            "high power", "power hungry"
        ]):
            messages.append(
                "Appliances that often use substantial electricity "
                "include air conditioners, electric water heaters, "
                "space heaters, electric cooking equipment, and "
                "clothes dryers. Actual consumption depends on their "
                "power rating and how long they operate."
            )

        elif any(word in q for word in [
            "unit", "kwh", "kilowatt", "what is energy consumption"
        ]):
            messages.append(
                "One kilowatt-hour (kWh), commonly called one electricity "
                "unit, is the energy used by a 1,000-watt appliance "
                "running for one hour. For example, a 100-watt bulb "
                "running for 10 hours uses 1 kWh."
            )

        elif any(word in q for word in [
            "solar", "solar panel", "renewable energy"
        ]):
            messages.append(
                "Solar panels can reduce electricity purchased from "
                "the grid when they generate power. The benefit depends "
                "on sunlight, panel capacity, installation cost, and "
                "your electricity tariff."
            )

        elif any(word in q for word in [
            "standby", "switch off", "unplug"
        ]):
            messages.append(
                "Turning off devices when they are not needed can reduce "
                "standby consumption. Unplug chargers and equipment when "
                "practical, while keeping essential safety and monitoring "
                "devices connected."
            )

        elif any(word in q for word in [
            "high bill", "bill increased", "bill is high",
            "why is my bill"
        ]):
            messages.append(
                "A higher electricity bill can result from increased "
                "appliance use, air conditioning, water heating, "
                "seasonal changes, tariff changes, or estimated meter "
                "readings. Compare your kWh usage across billing periods "
                "and check your bill's unit rate and billing dates."
            )

        elif any(word in q for word in [
            "forecast", "predict", "next month", "future consumption"
        ]):
            if recent_average > 0:
                messages.append(
                    f"Your recent average consumption is "
                    f"{recent_average:.2f} kWh, and the current "
                    f"estimate is {forecast:.2f} kWh. "
                    "This is a basic estimate, not a guarantee."
                )
            else:
                messages.append(
                    "I can explain energy forecasting, but I need "
                    "your saved readings to provide a personalized "
                    "consumption estimate."
                )

        elif any(word in q for word in [
            "temperature", "weather", "hot", "humidity"
        ]):
            if temperature is not None or humidity is not None:
                details = []
                if temperature is not None:
                    details.append(f"{temperature}°C")
                if humidity is not None:
                    details.append(f"{humidity}% humidity")

                messages.append(
                    "Weather context: " + ", ".join(details) +
                    ". Hot or humid conditions can increase cooling "
                    "and fan usage, depending on your appliances."
                )
            else:
                messages.append(
                    "Weather can affect electricity use, especially "
                    "through air conditioning and fans. Enter a location "
                    "in the weather panel to view current conditions."
                )

        elif any(word in q for word in [
            "anomaly", "unusual", "abnormal", "spike"
        ]):
            messages.append(
                "An unusual consumption spike can be caused by "
                "high-power appliances, longer operating hours, "
                "or a meter-reading issue. Compare your recent readings "
                "and check which appliances were operating."
            )

        elif any(word in q for word in [
            "thank", "thanks"
        ]):
            messages.append(
                "You're welcome! Ask me whenever you need help "
                "understanding or reducing your energy consumption."
            )

        else:
            messages.append(
                "I can help with electricity bills, energy units, "
                "appliance consumption, energy-saving tips, solar power, "
                "weather-related usage, and consumption forecasting. "
                "Could you ask your question in one of those areas?"
            )

    # ---------------------------------------------
    # PERSONAL CONSUMPTION INSIGHTS
    # ---------------------------------------------

    if recent_average > 0:
        if forecast > recent_average * 1.20:
            messages.append(
                "Your estimated consumption is more than 20% above "
                "your recent average. Consider reviewing appliance "
                "usage and checking for unexpected consumption."
            )
        elif forecast < recent_average * 0.80:
            messages.append(
                "Your estimated consumption is more than 20% below "
                "your recent average."
            )
        else:
            messages.append(
                "Your estimated consumption is close to your "
                "recent average."
            )

    if anomaly:
        messages.append(
            "An unusual consumption pattern was detected. "
            "Review your readings and check whether high-power "
            "appliances were used for longer than usual."
        )

    if temperature is not None and temperature >= 32:
        messages.append(
            "High temperatures may increase cooling-related "
            "electricity consumption."
        )

    if humidity is not None and humidity >= 80:
        messages.append(
            "High humidity may increase the use of fans or "
            "air conditioning."
        )

    if not messages:
        messages.append(
            "I'm your GridPulseAI Energy Advisor. Ask me about "
            "electricity bills, appliances, or energy-saving tips."
        )

    return " ".join(messages)
