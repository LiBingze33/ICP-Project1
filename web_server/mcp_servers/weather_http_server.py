from typing import Any
import httpx
from fastmcp import FastMCP
from database.db import SessionLocal
from database.model import User
from middleware.auth import require_local_user, require_local_admin

# Child MCP server only
weather_mcp = FastMCP("weather")

NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"


async def make_nws_request(url: str) -> dict[str, Any] | None:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


def format_alert(feature: dict) -> str:
    props = feature["properties"]
    return f"""
Event: {props.get("event", "Unknown")}
Area: {props.get("areaDesc", "Unknown")}
Severity: {props.get("severity", "Unknown")}
Description: {props.get("description", "No description available")}
Instructions: {props.get("instruction", "No specific instructions provided")}
""".strip()


@weather_mcp.prompt()
async def bing_weather_style() -> str:
    return (
        "When presenting any result from the weather server, "
        "always begin with the sentence: "
        "'This message is from bing weather MCP server.'"
    )


@weather_mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    state = state.strip().upper()

    if len(state) != 2 or not state.isalpha():
        return "Invalid state code. Please provide a two-letter US state code."

    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)


@weather_mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    if not (-90 <= latitude <= 90):
        return "Invalid latitude. It must be between -90 and 90."

    if not (-180 <= longitude <= 180):
        return "Invalid longitude. It must be between -180 and 180."

    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    forecast_url = points_data.get("properties", {}).get("forecast")
    if not forecast_url:
        return "Forecast URL not found for this location."

    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    periods = forecast_data.get("properties", {}).get("periods", [])
    if not periods:
        return "No forecast periods available."

    forecasts = []
    for period in periods[:5]:
        forecast = f"""
{period.get("name", "Unknown period")}:
Temperature: {period.get("temperature", "Unknown")}°{period.get("temperatureUnit", "")}
Wind: {period.get("windSpeed", "Unknown")} {period.get("windDirection", "")}
Forecast: {period.get("detailedForecast", "No forecast available")}
""".strip()
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)


@weather_mcp.tool(auth=require_local_user)
async def get_user_info() -> dict:
    """Return the currently authenticated user's GitHub and local role info."""
    from fastmcp.server.dependencies import get_access_token

    token = get_access_token()
    github_login = token.claims.get("login")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.github_login == github_login).first()

        return {
            "github_user": github_login,
            "name": token.claims.get("name"),
            "email": token.claims.get("email"),
            "role": user.role if user else None,
        }
    finally:
        db.close()


@weather_mcp.tool(auth=require_local_admin)
async def only_tool() -> str:
    """Example admin-only tool."""
    return "message is 299."