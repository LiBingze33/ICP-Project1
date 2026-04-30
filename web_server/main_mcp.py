# import os
# from dotenv import load_dotenv
# from fastmcp import FastMCP
# from fastmcp.server.auth.providers.github import GitHubProvider

# from mcp_servers.weather_http_server import weather_mcp
# from mcp_servers.local_file_server import file_mcp

# load_dotenv()

# GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
# GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

# if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
#     raise ValueError("Missing GitHub OAuth credentials.")
# #prepare for the https
# auth = GitHubProvider(
#     client_id=GITHUB_CLIENT_ID,
#     client_secret=GITHUB_CLIENT_SECRET,
#     base_url="https://9163.syslab.au",
#     issuer_url="https://9163.syslab.au",
# )

# main_mcp = FastMCP("main_server", auth=auth)

# # Mount child servers
# main_mcp.mount(weather_mcp, namespace="weather")
# main_mcp.mount(file_mcp, namespace="files")

# if __name__ == "__main__":
#     main_mcp.run(transport="http", host="127.0.0.1", port=9000)
from fastmcp import FastMCP

from mcp_servers.weather_http_server import weather_mcp
from mcp_servers.local_file_server import file_mcp

main_mcp = FastMCP("main_server")

# Mount child servers
main_mcp.mount(weather_mcp, namespace="weather")
main_mcp.mount(file_mcp, namespace="files")


@main_mcp.prompt()
async def general_style() -> str:
    return (
        "You are a helpful assistant. "
        "Answer the user's question clearly. "
        "Do not claim to have used external tools unless tool results are provided."
    )


if __name__ == "__main__":
    main_mcp.run(transport="http", host="127.0.0.1", port=9000)