import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider

from mcp_servers.weather_http_server import weather_mcp
from mcp_servers.local_file_server import file_mcp

load_dotenv(".env", override=True)

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
    raise ValueError("Missing GitHub OAuth credentials.")

auth = GitHubProvider(
    client_id=GITHUB_CLIENT_ID,
    client_secret=GITHUB_CLIENT_SECRET,
    base_url="http://127.0.0.1:9000",
)

main_mcp = FastMCP("main_server", auth=auth)

# Mount child servers
main_mcp.mount(weather_mcp, namespace="weather")
main_mcp.mount(file_mcp, namespace="files")

if __name__ == "__main__":
    main_mcp.run(transport="http", host="127.0.0.1", port=9000)