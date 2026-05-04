from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Dict, Optional

import mcp.types as mcp_types
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult

class FileMiddleware(Middleware):
    """FastMCP middleware for handling security"""
    def __init__(
        self,
        workspace_root: Path,
        *,
        permissions: Optional[Dict[str, bool]] = None,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.permissions = permissions or {
            "read": True,
            "write": True,
            "delete": True,
            "modify": True,
        }
    
    sensitive_files={
        ".env",
        ".env.local",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "config.yaml"
    }
    
    sensitive_suffixes = {".key", ".pem", ".p12", ".pfx"}
    
    #prompt injection prevention
    prompt_injection_patterns = (
        re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+promt", re.IGNORECASE),
        re.compile(r"developer\s+message", re.IGNORECASE),
        re.compile(r"tool\s*:\s*.*", re.IGNORECASE),
        re.compile(r"<\s*script", re.IGNORECASE),
    )
    
    secret_patterns = (
        re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|secret|password)\b\s*[:=]\s*\S+"),
        re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
        re.compile(r"gh[pousr]_[A-Za-z0-9_]+"),
    )
    
    XSS_patterns = (
        re.compile(r"<\s*script", re.IGNORECASE),
        re.compile(r"javascript\s*:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
    )
    
    sql_patterns = (
        re.compile(r"(?i)\b(select|insert|update|delete|drop|union|--|;)\b"),
        re.compile(r"(?i)\b(or|and)\b\s+\d+=\d+"),
        re.compile(r"(?i)\b(exec|execute|xp_cmdshell|sp_executesql)\b"),
        re.compile(r"(?i)\bunion\b\s+\bselect\b"),
        re.compile(r"(?i)\bdrop\b\s+\btable\b"),
        re.compile(r"(?i)\bor\b\s+1\s*=\s*1\b"),
        re.compile(r"(?i)['\"`;]\s*--"),            
    )

def __init__(self, workspace_root: Path, *, permissions: dict[str,bool] | None = None,) ->None:
        self.workspace_root = workspace_root.resolve()
        self.permissions = permissions or {
            "read": True,
            "write": False,
            "delete": False,
            "modify": False,
        }   
        
async def on_call_tool(
    self,
    context: MiddlewareContext[mcp_types.CallToolRequestParams],
    call_next: CallNext[mcp_types.CallToolRequestParams, ToolResult],
) -> ToolResult:
    tool_name = context.message.name
    if tool_name not in {"list_files", "read_file", "create_file", "delete_file", "modify_file"}:
        return await call_next(context)
    
    arguments = dict(context.message.arguments or {})
    file_name = arguments.get("file_name")
    
    if tool_name == "list_files":
        if not self.permissions.get("read", False):
            raise PermissionError("Read permission denied.")
        return await call_next(context)
    
    resolved_path = self.validate_path(file_name)
    self._check_operation_policy(tool_name, arguments, resolved_path)
    
    if tool_name == "create_file" and "content" in arguments:
        arguments["content"] = self.sanitize_content(arguments["content"])  
        context = context.copy(message=context.message.copy(arguments=arguments))
        return await call_next(context)
    result = await call_next(context)
    if tool_name == "read_file":
        self.inspect_read_result(result)
        return result
    
def validate_path(self, file_name: Any) -> Path:
    #reject empty or non-string paths before touching the file system
    
    if not isinstance(file_name, str) or not file_name.strip():
        raise ValueError("Invalid file name.")
    
    candidate_path = Path(file_name)
    #block absolute paths and paths with parent directory references
    if candidate_path.is_absolute() or ".." in candidate_path.parts:
        raise ValueError("Invalid file path.")
    
    resolved_path = (self.workspace_root / candidate_path).resolve()
    
    #keep every file operation restrcited to the approved workspace only
    if self.workspace_root != resolved_path and self.workspace_root not in resolved_path.parents:
        raise ValueError("File path is outside the allowed workspace.")
    
    #block obvious secret-bearing file names and key material even inside the workspace
    lowered_name = candidate_path.name.lower()
    if lowered_name in self.sensitive_files or any(lowered_name.endswith(suffix) for suffix in self.sensitive_suffixes):
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
    }[tool_name]
    self._check_permission(operation)

    # Enforce an explicit confirmation flag before any delete can proceed.
    if tool_name == "delete_file" and arguments.get("confirm") is not True:
        raise ValueError("delete_file requires confirm=True.")

    if tool_name == "create_file":
        content = str(arguments.get("content", ""))
        self._reject_unsafe_input(path.name)
        self._reject_unsafe_input(content)

    if tool_name in {"read_file", "delete_file"}:
        self._reject_unsafe_input(path.name)

def _check_permission(self, operation: str) -> None:
    # Central CRUD permission gate so future policy changes stay in one place.
    if not self.permissions.get(operation, False):
        raise PermissionError(f"{operation.title()} permission denied.")

def _reject_unsafe_input(self, value: str) -> None:
    # Reject common XSS payload shapes before content reaches a file tool.
    if any(pattern.search(value) for pattern in self.XSS_PATTERNS):
        raise ValueError("Input contains a blocked XSS pattern.")

    # Reject common SQL injection probes to reduce unsafe prompt and content handling.
    if any(pattern.search(value) for pattern in self.SQLI_PATTERNS):
        raise ValueError("Input contains a blocked SQL injection pattern.")

def sanitise_input(self, value: str) -> str:
    # Escape HTML-special characters so stored content does not preserve raw script tags.
    return html.escape(value, quote=False)

def inspect_read_result(self, result: ToolResult) -> None:
    text_output = "\n".join(
    block.text for block in result.content if getattr(block, "type", None) == "text"
    )

    # Inspect file reads for prompt-injection strings that could steer later model behavior.
    if any(pattern.search(text_output) for pattern in self.PROMPT_INJECTION_PATTERNS):
        raise ValueError("read_file output contains prompt injection content.")

    # Block read responses that look like secrets or private key material.
    if any(pattern.search(text_output) for pattern in self.SECRET_PATTERNS):
        raise ValueError("read_file output appears to contain secrets.")