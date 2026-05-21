from fastmcp import FastMCP

from middleware.internal_jwt import InternalJWTMiddleware
from mcp_servers.weather_http_server import weather_mcp
from mcp_servers.local_file_server import file_mcp
from mcp_servers.admin_server import admin_mcp
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware

main_mcp = FastMCP("main_server")

# Add JWT middleware to the parent MCP server.
# This checks the internal token before requests reach mounted child servers.
main_mcp.add_middleware(InternalJWTMiddleware())

main_mcp.add_middleware(RateLimitingMiddleware(
    #allow 5 requests per second 
    max_requests_per_second=5.0,
    #but allow 10 quick requests at once
    burst_capacity=10
))
#response limitation
main_mcp.add_middleware(ResponseLimitingMiddleware(max_size=100_000))
# Mount child servers
main_mcp.mount(weather_mcp, namespace="weather")
main_mcp.mount(file_mcp, namespace="files")
main_mcp.mount(admin_mcp, namespace="admin")

@main_mcp.prompt()
async def general_style() -> str:
    return (
        "You are a helpful assistant. "
        "Answer the user's question clearly. "
        "Do not claim to have used external tools unless tool results are provided."
    )


if __name__ == "__main__":
    main_mcp.run(transport="http", host="127.0.0.1", port=9000)