from fastmcp import FastMCP

from database.db import SessionLocal
from database.model import User
admin_mcp = FastMCP("admin_server")


@admin_mcp.tool()
async def list_users() -> str:
    db = SessionLocal()

    try:
        users = db.query(User).order_by(User.user_id).all()
        if not users:
            return "There are currently no users in the database."

        lines = [
            f"Total users: {len(users)}",
            "",
            "Users:",
        ]

        for user in users:
            lines.append(
                f" {user.github_login} | role: {user.role}"
            )

        return "\n".join(lines)

    finally:
        db.close()

@admin_mcp.prompt()
async def admin_style() -> str:
    return (
        "You are an admin assistant. "
        "Use admin tools only when they are available. "
        "Do not guess database information. "
        "If admin tools are not available, say that admin permission is required."
    )