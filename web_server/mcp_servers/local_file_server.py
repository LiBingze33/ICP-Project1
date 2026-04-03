from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("file_server")
#Creates a FastMCP server object
BASE_DIR = Path(__file__).parent / "demo_docs"
BASE_DIR.mkdir(exist_ok=True)


@mcp.prompt()
async def file_style() -> str:
    return (
        "When presenting any result from the file MCP server, "
        "always begin with the sentence: "
        "'This message is from the Bing file MCP server.'"
    )


@mcp.tool()
async def list_files() -> str:
    """List files in the demo_docs folder."""
    files = []
    #iterdir() go through everything inside this folder
    for p in BASE_DIR.iterdir():
        #is_file() check whether this path is a file
        if p.is_file():
            files.append(p.name)

    if not files:
        return "No files found."

    return "\n".join(files)


@mcp.tool()
async def read_file(filename: str) -> str:
    """Read a file from the demo_docs folder.

    Args:
        filename: Name of the file to read
    """
    path = BASE_DIR / filename

    if not path.exists():
        return f"File '{filename}' does not exist."

    if not path.is_file():
        return f"'{filename}' is not a file."

    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return f"Unable to read file '{filename}'."
@mcp.tool()
async def create_file(filename: str, content: str) -> str:
    """Create a file inside the demo_docs folder.

    Args:
        filename: Name of the file to create
        content: Text content to write into the file
    """
    path = BASE_DIR / filename

    if path.exists():
        return f"File '{filename}' already exists."

    try:
        path.write_text(content, encoding="utf-8")
        return f"File '{filename}' created successfully."
    except Exception:
        return f"Unable to create file '{filename}'."
@mcp.tool()
async def delete_file(filename: str) -> str:
    """Delete a file from the demo_docs folder.

    Args:
        filename: Name of the file to delete
    """
    path = BASE_DIR / filename

    if not path.exists():
        return f"File '{filename}' does not exist."

    if not path.is_file():
        return f"'{filename}' is not a file."

    try:
        path.unlink()
        return f"File '{filename}' deleted successfully."
    except Exception:
        return f"Unable to delete file '{filename}'."
if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=9001)