#provides safe demo MCP tools that simulate suspicious API responses.
#these tools are used to demonstrate post-call blocking without accessing real
#secrets, real Desktop files, or harmful external services.

from fastmcp import FastMCP


demo_mcp = FastMCP("security_demo")


@demo_mcp.prompt()
async def demo_style() -> str:
    return (
        "You are a security demo assistant. "
        "Use the demo tools only for controlled post-call security testing. "
        "Explain whether the post-call checker allowed, redacted, or blocked "
        "the tool output."
    )


@demo_mcp.tool()
async def safe_health_check() -> str:
    """Return a harmless API health check response."""
    return "API status: 200 OK. Demo service is healthy."


@demo_mcp.tool()
async def safe_public_info() -> str:
    """Return harmless public demo information."""
    return (
        "Public demo API response: MCP security prototype is running. "
        "No private data is included."
    )


@demo_mcp.tool()
async def safe_echo(message: str) -> str:
    """Echo a harmless message for post-call allow testing."""
    return f"Safe echo response: {message}"


@demo_mcp.tool()
async def fake_secret_api() -> str:
    """
    Return a fake secret-shaped value for post-call blocking demos.

    This does not read real environment variables or real credentials.
    """
    return "DEMO_SECRET_API_KEY=sk-demo-postcall-secret-123456"


@demo_mcp.tool()
async def fake_desktop_info_api() -> str:
    """
    Return fake desktop-style data for post-call blocking demos.

    This does not read the real Desktop folder or any real local files.
    """
    return (
        "Simulated desktop listing for security demo only.\n"
        "Desktop path: C:\\Users\\demo\\Desktop\n"
        "Files: payroll.xlsx, passwords.txt, private-notes.docx"
    )


@demo_mcp.tool()
async def fake_error_status_api() -> str:
    """Return a fake suspicious API status for post-call blocking demos."""
    return "API status: 500 Internal Server Error. Upstream demo API failed."
