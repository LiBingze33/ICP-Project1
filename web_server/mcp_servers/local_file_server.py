from pathlib import Path
from fastmcp import FastMCP

file_mcp = FastMCP("file_server")

BASE_DIR = Path(__file__).parent / "demo_docs"
BASE_DIR.mkdir(exist_ok=True)


def safe_path(filename: str) -> Path | None:
    # Only allow plain filenames inside demo_docs
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None
    return BASE_DIR / filename


@file_mcp.prompt()
async def file_style() -> str:
    return (
        "When presenting any result from the file MCP server, "
        "always begin with the sentence: "
        "'This message is from the Bing file MCP server.'"
    )


@file_mcp.tool()
async def list_files() -> str:
    """List files in the demo_docs folder."""
    files = [p.name for p in BASE_DIR.iterdir() if p.is_file()]
    return "No files found." if not files else "\n".join(files)


@file_mcp.tool()
async def read_file(filename: str) -> str:
    """Read a file from the demo_docs folder."""
    path = safe_path(filename)
    if path is None:
        return "Invalid filename."

    if not path.exists():
        return f"File '{filename}' does not exist."

    if not path.is_file():
        return f"'{filename}' is not a file."

    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return f"Unable to read file '{filename}'."


@file_mcp.tool()
async def create_file(filename: str, content: str) -> str:
    """Create a file inside the demo_docs folder."""
    path = safe_path(filename)
    if path is None:
        return "Invalid filename."

    if path.exists():
        return f"File '{filename}' already exists."

    try:
        path.write_text(content, encoding="utf-8")
        return f"File '{filename}' created successfully."
    except Exception:
        return f"Unable to create file '{filename}'."


@file_mcp.tool()
async def delete_file(filename: str) -> str:
    """Delete a file from the demo_docs folder."""
    path = safe_path(filename)
    if path is None:
        return "Invalid filename."

    if not path.exists():
        return f"File '{filename}' does not exist."

    if not path.is_file():
        return f"'{filename}' is not a file."

    try:
        path.unlink()
        return f"File '{filename}' deleted successfully."
    except Exception:
        return f"Unable to delete file '{filename}'."