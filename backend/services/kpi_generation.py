from backend.models import KPI

def generate_weather_kpi(data: dict) -> KPI:
    """Generates a new KPI based on the given weather data."""
    return KPI(
        id="kpi_weather_" + data["city"].lower(),
        name=f"Weather KPI for {data['city']}",
        description=f"A KPI that tracks the temperature in {data['city']}",
        formula="temperature * 2",
    )
