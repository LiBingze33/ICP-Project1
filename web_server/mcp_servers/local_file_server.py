from pathlib import Path
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token

file_mcp = FastMCP("file_server")

BASE_DIR = Path(__file__).parent / "../demo_docs"
BASE_DIR.mkdir(exist_ok=True)

def get_current_username() -> str:
    # Get current user information from OAuth token
    token = get_access_token()
    claims = getattr(token, "claims", {}) or {}

    username = (
        claims.get("login")
        or claims.get("preferred_username")
        or claims.get("username")
        or claims.get("sub")
        or "unknown_user"
    )

    # Keep username safe for folder names
    safe_username = "".join(
        c for c in str(username) if c.isalnum() or c in ("_", "-")
    )

    return safe_username or "unknown_user"

def get_user_dir() -> Path:
    # Each user gets their own private folder
    username = get_current_username()
    user_dir = BASE_DIR / username
    user_dir.mkdir(exist_ok=True)

    # Auto-create a default file for first-time users
    default_file = user_dir / "user_notes.txt"
    if not default_file.exists():
        default_file.write_text(
            f"This is the private file for {username}.",
            encoding="utf-8"
        )

    return user_dir


def safe_path(filename: str) -> Path | None:
    # Only allow plain filenames inside the current user's private folder
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None

    user_dir = get_user_dir()
    return user_dir / filename


@file_mcp.prompt()
async def file_style() -> str:
    return (
        "When presenting any result from the file MCP server, "
        "always begin with the sentence: "
        "'This message is from the Bing file MCP server.'"
    )


@file_mcp.tool()
async def list_files() -> str:
    """List files in the current user's private folder."""
    user_dir = get_user_dir()

    files = [p.name for p in user_dir.iterdir() if p.is_file()]

    return "No files found in your private folder." if not files else "\n".join(files)


@file_mcp.tool()
async def read_file(filename: str) -> str:
    """Read a file from the current user's private folder."""
    path = safe_path(filename)

    if path is None:
        return "Invalid filename."

    if not path.exists():
        return f"File '{filename}' does not exist in your private folder."

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