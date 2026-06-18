
# User prompt in web app
# -> main.py
# -> run_agent() in services/mcp_host.py
# -> MCP tool is called
# -> post-call checker runs
# -> audit logger writes post_call_audit.logfrom __future__ import annotations

#the trigger is in services/mcp_host.py 
#async def call_mcp_tool_with_postcheck()
#Then call await write_post_call_audit()
# --> log_post_call_event --> writes to web_server/secuirty/post_call_audit.log
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


DEFAULT_AUDIT_LOG = Path(__file__).resolve().parent / "post_call_audit.log"

SENSITIVE_AUDIT_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "client_secret",
    "content",
    "internal_jwt",
    "password",
    "secret",
    "token",
    "workspace_path",
}


def log_post_call_event(
    event: dict[str, Any],
    audit_log_path: Path = DEFAULT_AUDIT_LOG,
) -> None:
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **sanitize_for_audit(event),
    }

    with audit_log_path.open("a", encoding="utf-8") as audit_file:
        audit_file.write(json.dumps(record, sort_keys=True) + "\n")


def sanitize_for_audit(value: Any, key: str | None = None) -> Any:
    if key and key.lower() in SENSITIVE_AUDIT_KEYS:
        return "[redacted]"

    if isinstance(value, dict):
        return {
            str(item_key): sanitize_for_audit(item_value, str(item_key))
            for item_key, item_value in value.items()
        }

    if isinstance(value, list):
        return [sanitize_for_audit(item) for item in value]

    if isinstance(value, tuple):
        return [sanitize_for_audit(item) for item in value]

    if isinstance(value, str):
        return value if len(value) <= 200 else value[:200] + "...[truncated]"

    return value
