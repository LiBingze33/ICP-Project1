from typing import Any
import httpx
from fastmcp import FastMCP
from fastmcp.dependencies import Depends
# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"


async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get("event", "Unknown")}
Area: {props.get("areaDesc", "Unknown")}
Severity: {props.get("severity", "Unknown")}
Description: {props.get("description", "No description available")}
Instructions: {props.get("instruction", "No specific instructions provided")}
"""


@mcp.prompt()
async def bing_weather_style() -> str:
    return (
        "When presenting any result from the weather server, "
        "always begin with the sentence: "
        "'This message is from bing weather server.'"
    )


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:
        forecast = f"""
{period["name"]}:
Temperature: {period["temperature"]}°{period["temperatureUnit"]}
Wind: {period["windSpeed"]} {period["windDirection"]}
Forecast: {period["detailedForecast"]}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)


# ==========================================================
# CHOOSE ONE VERSION BELOW FOR TESTING
# ==========================================================

# -------------------------
# UNSAFE VERSION
# Uncomment this block when testing the unsafe design
# -------------------------
@mcp.tool()
async def get_saved_weather_preferences(user_id: str) -> str:
    """UNSAFE: user_id is provided directly by the LLM/client."""
    fake_db = {
        "user_123": "Saved location: Los Angeles, CA",
        "admin_001": "Saved location: Washington, DC",
        "user_999": "Saved location: New York, NY",
    }

    result = fake_db.get(user_id)
    if not result:
        return f"No saved preferences found for {user_id}."

    return f"User {user_id} preferences: {result}"


# -------------------------
# SAFE VERSION
# Uncomment this block when testing the safe design
# -------------------------
# def get_current_user_id() -> str:
#     """Injected by the trusted server, not chosen by the LLM."""
#     return "user_123"


# @mcp.tool()
# async def get_saved_weather_preferences(user_id: str = Depends(get_current_user_id)) -> str:
#     """SAFE: user_id is hidden from the LLM and injected by the server."""
#     fake_db = {
#         "user_123": "Saved location: Los Angeles, CA",
#         "admin_001": "Saved location: Washington, DC",
#         "user_999": "Saved location: New York, NY",
#     }

#     result = fake_db.get(user_id)
#     if not result:
#         return f"No saved preferences found for {user_id}."

#     return f"User {user_id} preferences: {result}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()