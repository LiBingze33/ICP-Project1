from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

import mcp.types as mcp_types
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult


class FileMiddleware(Middleware):
    """FastMCP middleware that enforces file tool security rules."""

    SENSITIVE_FILES = {
        ".env",
        ".env.local",
        "credentials.json",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "config.yaml",
    }

    SENSITIVE_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}

    PROMPT_INJECTION_PATTERNS = (
        re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+prompt", re.IGNORECASE),
        re.compile(r"developer\s+message", re.IGNORECASE),
        re.compile(r"tool\s*:\s*.*", re.IGNORECASE),
        re.compile(r"<\s*script", re.IGNORECASE),
    )

    SECRET_PATTERNS = (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|secret|password)\b\s*[:=]\s*\S+"
        ),
        re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
        re.compile(r"gh[pousr]_[A-Za-z0-9_]+"),
    )

    XSS_PATTERNS = (
        re.compile(r"<\s*script", re.IGNORECASE),
        re.compile(r"javascript\s*:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
    )

    SQLI_PATTERNS = (
        re.compile(r"(?i)\bunion\b\s+\bselect\b"),
        re.compile(r"(?i)\bdrop\b\s+\btable\b"),
        re.compile(r"(?i)\b(exec|execute|xp_cmdshell|sp_executesql)\b"),
        re.compile(r"(?i)['\"]\s*(or|and)\s+\d+\s*=\s*\d+"),
        re.compile(r"(?i)\b(or|and)\b\s+\d+\s*=\s*\d+\s*(--|#)?"),
        re.compile(r"(?i)['\"`;]\s*--"),
    )

    def __init__(
        self,
        workspace_root: Path,
        *,
        permissions: Optional[Dict[str, bool]] = None,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.permissions = permissions or {
            "read": True,
            "create": True,
            "modify": True,
            "delete": True,
        }

    async def on_call_tool(
        self,
        context: MiddlewareContext[mcp_types.CallToolRequestParams],
        call_next: CallNext[mcp_types.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        tool_name = context.message.name
        if tool_name not in {
            "list_files",
            "read_file",
            "create_file",
            "delete_file",
            "show_file_path",
        }:
            return await call_next(context)

        arguments = dict(context.message.arguments or {})

        if tool_name == "list_files":
            self._check_permission("read")
            return await call_next(context)

        filename = arguments.get("filename")
        resolved_path = self.validate_path(filename)
        self._check_operation_policy(tool_name, arguments, resolved_path)

        result = await call_next(context)

        if tool_name == "read_file":
            self.inspect_read_result(result)

        return result

    def validate_path(self, filename: Any) -> Path:
        # Reject empty or non-string paths before touching the filesystem.
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("Invalid file name.")

        candidate_path = Path(filename)

        # Block absolute paths and parent-directory traversal attempts.
        if candidate_path.is_absolute() or ".." in candidate_path.parts:
            raise ValueError("Invalid file path.")

        resolved_path = (self.workspace_root / candidate_path).resolve()

        # Keep all file operations inside the approved workspace folder.
        if (
            self.workspace_root != resolved_path
            and self.workspace_root not in resolved_path.parents
        ):
            raise ValueError("File path is outside the allowed workspace.")

        # Block obvious secret-bearing names and key material.
        lowered_name = candidate_path.name.lower()
        if lowered_name in self.SENSITIVE_FILES or any(
            lowered_name.endswith(suffix) for suffix in self.SENSITIVE_SUFFIXES
        ):
            raise ValueError("Access to sensitive file is denied.")

        return resolved_path

    def _check_operation_policy(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        path: Path,
    ) -> None:
        operation = {
            "read_file": "read",
            "create_file": "create" if not path.exists() else "modify",
            "delete_file": "delete",
            "show_file_path": "read",
        }[tool_name]
        self._check_permission(operation)

        # Require an explicit confirmation flag before any delete.
        if tool_name == "delete_file" and arguments.get("confirm") is not True:
            raise ValueError("delete_file requires confirm=True.")

        if tool_name == "create_file":
            content = str(arguments.get("content", ""))
            self._reject_unsafe_input(path.name)
            self._reject_unsafe_input(content)

        if tool_name in {"read_file", "delete_file", "show_file_path"}:
            self._reject_unsafe_input(path.name)

    def _check_permission(self, operation: str) -> None:
        if not self.permissions.get(operation, False):
            raise PermissionError(f"{operation.title()} permission denied.")

    @classmethod
    def reject_unsafe_text(cls, value: str) -> None:
        # Hard-block obvious XSS payloads before they can be written to disk.
        if any(pattern.search(value) for pattern in cls.XSS_PATTERNS):
            raise ValueError("Input contains a blocked XSS pattern.")

        # Hard-block classic SQL injection probes instead of storing them.
        if any(pattern.search(value) for pattern in cls.SQLI_PATTERNS):
            raise ValueError("Input contains a blocked SQL injection pattern.")

    def _reject_unsafe_input(self, value: str) -> None:
        self.reject_unsafe_text(value)

    def inspect_read_result(self, result: ToolResult) -> None:
        text_output = "\n".join(
            block.text
            for block in result.content
            if getattr(block, "type", None) == "text"
        )

        # Stop prompt-injection content from being returned through read_file.
        if any(pattern.search(text_output) for pattern in self.PROMPT_INJECTION_PATTERNS):
            raise ValueError("read_file output contains prompt injection content.")

        # Stop likely secrets or key material from being returned through read_file.
        if any(pattern.search(text_output) for pattern in self.SECRET_PATTERNS):
            raise ValueError("read_file output appears to contain secrets.")
