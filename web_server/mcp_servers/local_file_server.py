from pathlib import Path
from fastmcp import FastMCP

file_mcp = FastMCP("file_server")

# Default folder only used when no folder is provided
BASE_DIR = (Path(__file__).parent / "../demo_docs").resolve()
BASE_DIR.mkdir(exist_ok=True)


def get_path(path_text: str) -> Path | None:
    """
    Insecure path resolver for testing.
    Allows:
    - relative paths like ../demo_docs
    - absolute paths like /Users/...
    - home paths like ~/Desktop
    """
    if not path_text or not isinstance(path_text, str):
        return None

    return Path(path_text).expanduser().resolve()


@file_mcp.prompt()
async def file_style() -> str:
    return (
        "When presenting any result from the file MCP server, "
        "always begin with the sentence: "
        "'This message is from the Bing file MCP server.'"
    )


@file_mcp.tool()
async def current_directory() -> str:
    """Show the current working directory of the MCP server."""
    return str(Path.cwd())


@file_mcp.tool()
async def list_files(folder_path: str = "") -> str:
    """
    List files in a folder.
    If no folder_path is provided, list files in demo_docs.
    """
    if folder_path.strip():
        folder = get_path(folder_path)
    else:
        folder = BASE_DIR

    if folder is None:
        return "Invalid folder path."

    if not folder.exists():
        return f"Folder '{folder_path}' does not exist. Resolved path was: {folder}"

    if not folder.is_dir():
        return f"'{folder_path}' is not a folder. Resolved path was: {folder}"

    files = []

    try:
        for p in folder.rglob("*"):
            if p.is_file():
                files.append(str(p.relative_to(folder)))
    except Exception as e:
        return f"Unable to list files in '{folder_path}': {e}"

    return "No files found." if not files else "\n".join(files)


@file_mcp.tool()
async def read_file(filename: str) -> str:
    """Read a file from any provided path."""
    path = get_path(filename)

    if path is None:
        return "Invalid filename."

    if not path.exists():
        return f"File '{filename}' does not exist. Resolved path was: {path}"

    if not path.is_file():
        return f"'{filename}' is not a file. Resolved path was: {path}"

    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Unable to read file '{filename}': {e}"


@file_mcp.tool()
async def create_file(filename: str, content: str) -> str:
    """Create a file at any provided path."""
    path = get_path(filename)

    if path is None:
        return "Invalid filename."

    if path.exists():
        return f"File '{filename}' already exists. Resolved path was: {path}"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"File '{filename}' created successfully. Resolved path was: {path}"
    except Exception as e:
        return f"Unable to create file '{filename}': {e}"


@file_mcp.tool()
async def delete_file(filename: str) -> str:
    """Delete a file from any provided path."""
    path = get_path(filename)

    if path is None:
        return "Invalid filename."

    if not path.exists():
        return f"File '{filename}' does not exist. Resolved path was: {path}"

    if not path.is_file():
        return f"'{filename}' is not a file. Resolved path was: {path}"

    try:
        path.unlink()
        return f"File '{filename}' deleted successfully. Resolved path was: {path}"
    except Exception as e:
        return f"Unable to delete file '{filename}': {e}"