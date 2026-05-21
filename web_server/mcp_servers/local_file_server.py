from pathlib import Path

from fastmcp import FastMCP

from database.db import Base, SessionLocal, engine
from database.model import OwnedFile, User
from middleware import FileMiddleware
from middleware.auth import get_current_local_user_identity

file_mcp = FastMCP("file_server")

BASE_DIR = Path(__file__).parent / "demo_docs"
BASE_DIR.mkdir(exist_ok=True)
Base.metadata.create_all(bind=engine)
file_security = FileMiddleware(workspace_root=BASE_DIR)
file_mcp.add_middleware(file_security)


def safe_path(filename: str) -> Path | None:
    # Only allow plain filenames inside demo_docs
    if not filename or Path(filename).is_absolute() or "/" in filename or "\\" in filename or ".." in filename:
        return None
    return BASE_DIR / filename


def owned_storage_dir(user_id: int) -> Path:
    path = BASE_DIR / "_owned" / f"user_{user_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def owned_storage_path(user_id: int, filename: str) -> Path:
    return owned_storage_dir(user_id) / filename


def get_owned_file_record(db, user_id: int, logical_name: str) -> OwnedFile | None:
    return (
        db.query(OwnedFile)
        .filter(
            OwnedFile.owner_user_id == user_id,
            OwnedFile.logical_name == logical_name,
        )
        .first()
    )


def get_user_by_login(db, github_login: str) -> User | None:
    return (
        db.query(User)
        .filter(User.github_login == github_login)
        .first()
    )


def list_owned_filenames_for_user(db, user_id: int) -> str:
    records = (
        db.query(OwnedFile)
        .filter(OwnedFile.owner_user_id == user_id)
        .order_by(OwnedFile.logical_name.asc())
        .all()
    )

    files: list[str] = []
    stale_records: list[OwnedFile] = []
    for record in records:
        storage_path = owned_storage_path(user_id, record.logical_name)
        if storage_path.is_file():
            files.append(record.logical_name)
        else:
            stale_records.append(record)

    if stale_records:
        for record in stale_records:
            db.delete(record)
        db.commit()

    return "No files found." if not files else "\n".join(files)


@file_mcp.prompt()
async def file_style() -> str:
    return (
        "When presenting any result from the file MCP server, "
        "always begin with the sentence: "
        "'This message is from the Bing file MCP server.'"
    )


@file_mcp.tool()
async def list_files() -> str:
    """List only the current user's files."""
    user = get_current_local_user_identity()
    db = SessionLocal()
    try:
        return list_owned_filenames_for_user(db, int(user["user_id"]))
    finally:
        db.close()


@file_mcp.tool()
async def list_user_files(username: str) -> str:
    """List files for a username only when it matches the logged-in user."""
    requested_username = username.strip()
    if not requested_username:
        return "A username is required."

    current_user = get_current_local_user_identity()
    db = SessionLocal()
    try:
        requested_user = get_user_by_login(db, requested_username)
        if requested_user is None:
            return f"User '{requested_username}' does not exist."

        if requested_user.user_id != current_user["user_id"]:
            return "You can only view your own files."

        return list_owned_filenames_for_user(db, requested_user.user_id)
    finally:
        db.close()


@file_mcp.tool()
async def read_file(filename: str) -> str:
    """Read a file owned by the current user."""
    path = safe_path(filename)
    if path is None:
        return "Invalid filename."

    logical_name = path.name
    user = get_current_local_user_identity()
    db = SessionLocal()
    try:
        record = get_owned_file_record(db, user["user_id"], logical_name)
        if record is None:
            return f"File '{logical_name}' does not exist."

        storage_path = owned_storage_path(user["user_id"], logical_name)
        if not storage_path.exists() or not storage_path.is_file():
            db.delete(record)
            db.commit()
            return f"File '{logical_name}' does not exist."

        try:
            return storage_path.read_text(encoding="utf-8")
        except Exception:
            return f"Unable to read file '{logical_name}'."
    finally:
        db.close()


@file_mcp.tool()
async def create_file(filename: str, content: str) -> str:
    """Create a file owned by the current user."""
    path = safe_path(filename)
    if path is None:
        return "Invalid filename."

    logical_name = path.name
    storage_path = None
    db = SessionLocal()
    try:
        user = get_current_local_user_identity()
        if get_owned_file_record(db, user["user_id"], logical_name) is not None:
            return f"File '{logical_name}' already exists."

        file_security.reject_unsafe_text(logical_name)
        file_security.reject_unsafe_text(content)

        storage_path = owned_storage_path(user["user_id"], logical_name)
        if storage_path.exists():
            return f"File '{logical_name}' already exists."

        storage_path.write_text(content, encoding="utf-8")
        db.add(
            OwnedFile(
                owner_user_id=user["user_id"],
                logical_name=logical_name,
            )
        )
        db.commit()
        return f"File '{logical_name}' created successfully."
    except ValueError as exc:
        if storage_path is not None and storage_path.exists():
            storage_path.unlink()
        db.rollback()
        return f"Blocked unsafe file request: {exc}"
    except Exception:
        if storage_path is not None and storage_path.exists():
            storage_path.unlink()
        db.rollback()
        return f"Unable to create file '{logical_name}'."
    finally:
        db.close()


@file_mcp.tool()
async def show_file_path(filename: str) -> str:
    """Show the current user's resolved storage path for a file."""
    path = safe_path(filename)
    if path is None:
        return "Invalid filename."

    logical_name = path.name
    user = get_current_local_user_identity()
    resolved = owned_storage_path(user["user_id"], logical_name).resolve()
    if resolved.exists():
        return f"Resolved file path: {resolved}"
    return f"Resolved file path: {resolved} (file does not exist yet)"


@file_mcp.tool()
async def delete_file(filename: str, confirm: bool = False) -> str:
    """Delete a file owned by the current user."""
    if confirm is not True:
        return "Deletion not confirmed. Set 'confirm' to true to delete the file."

    path = safe_path(filename)
    if path is None:
        return "Invalid filename."

    logical_name = path.name
    user = get_current_local_user_identity()
    db = SessionLocal()
    try:
        record = get_owned_file_record(db, user["user_id"], logical_name)
        if record is None:
            return f"File '{logical_name}' does not exist."

        storage_path = owned_storage_path(user["user_id"], logical_name)
        if storage_path.exists() and not storage_path.is_file():
            return f"'{logical_name}' is not a file."

        if storage_path.exists():
            storage_path.unlink()

        db.delete(record)
        db.commit()
        return f"File '{logical_name}' deleted successfully."
    except Exception:
        db.rollback()
        return f"Unable to delete file '{logical_name}'."
    finally:
        db.close()
