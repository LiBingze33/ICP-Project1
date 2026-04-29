from pathlib import Path
from fastmcp import FastMCP

file_mcp = FastMCP("file_server")

# This should match the workspace root used in main.py
BASE_WORKSPACE_DIR = Path("user_workspaces").resolve()
BASE_WORKSPACE_DIR.mkdir(exist_ok=True)


def get_user_dir(workspace_path: str) -> Path | None:
    """
    Convert workspace_path into a safe Path.
    Only allow folders inside BASE_WORKSPACE_DIR.
    """
    if not workspace_path:
        return None

    user_dir = Path(workspace_path).resolve()

    # Make sure the path is still inside user_workspaces
    try:
        user_dir.relative_to(BASE_WORKSPACE_DIR)
    except ValueError:
        return None

    user_dir.mkdir(parents=True, exist_ok=True)

    return user_dir

def safe_path(filename: str, workspace_path: str) -> Path | None:
    """
    Only allow plain filenames inside the logged-in user's workspace folder.
    """
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None

    user_dir = get_user_dir(workspace_path)
    if user_dir is None:
        return None

    return user_dir / filename


@file_mcp.prompt()
async def file_style() -> str:
    return (
        "When presenting any result from the file MCP server, "
        "always begin with the sentence: "
        "'This message is from the Bing file MCP server.'"
    )


@file_mcp.tool()
async def list_files(workspace_path: str = "") -> str:
    """List files in the current user's private workspace folder."""
    user_dir = get_user_dir(workspace_path)

    if user_dir is None:
        return "Invalid user workspace."

    files = [p.name for p in user_dir.iterdir() if p.is_file()]

    return "No files found in your private folder." if not files else "\n".join(files)


@file_mcp.tool()
async def read_file(filename: str, workspace_path: str = "") -> str:
    """Read a file from the current user's private workspace folder."""
    path = safe_path(filename, workspace_path)

    if path is None:
        return "Invalid filename or user workspace."

    if not path.exists():
        return f"File '{filename}' does not exist in your private folder."

    if not path.is_file():
        return f"'{filename}' is not a file."

    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return f"Unable to read file '{filename}'."


@file_mcp.tool()
async def create_file(filename: str, content: str, workspace_path: str = "") -> str:
    """Create a file inside the current user's private workspace folder."""
    path = safe_path(filename, workspace_path)

    if path is None:
        return "Invalid filename or user workspace."

    if path.exists():
        return f"File '{filename}' already exists."

    try:
        path.write_text(content, encoding="utf-8")
        return f"File '{filename}' created successfully."
    except Exception:
        return f"Unable to create file '{filename}'."


@file_mcp.tool()
async def delete_file(filename: str, workspace_path: str = "") -> str:
    """Delete a file from the current user's private workspace folder."""
    path = safe_path(filename, workspace_path)

    if path is None:
        return "Invalid filename or user workspace."

    if not path.exists():
        return f"File '{filename}' does not exist."

    if not path.is_file():
        return f"'{filename}' is not a file."

    try:
        path.unlink()
        return f"File '{filename}' deleted successfully."
    except Exception:
        return f"Unable to delete file '{filename}'."