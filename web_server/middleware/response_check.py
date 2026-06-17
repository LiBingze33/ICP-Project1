from __future__ import annotations

from dataclasses import dataclass
import html
import re
from urllib.parse import unquote


@dataclass(frozen=True)
class ResponseCheckResult:
    text: str
    blocked: bool = False
    modified: bool = False
    reason: str = ""


SECRET_PATTERNS = (
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|"
        r"oauth[_-]?storage[_-]?encryption[_-]?key|internal[_-]?jwt[_-]?secret|"
        r"password|secret)\b\s*[:=]\s*['\"]?[^\s'\"<>]{6,}"
    ),
    re.compile(r"(?i)\bOPENROUTER_API_KEY\b"),
    re.compile(r"(?i)\bGITHUB_CLIENT_SECRET\b"),
    re.compile(r"(?i)\bOAUTH_STORAGE_ENCRYPTION_KEY\b"),
    re.compile(r"(?i)\bINTERNAL_JWT_SECRET\b"),
    re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
)

PROMPT_INJECTION_PATTERNS = (
    re.compile(r"(?i)\bignore\s+(?:all\s+)?previous\s+instructions\b"),
    re.compile(r"(?i)\breveal\s+(?:the\s+)?system\s+prompt\b"),
    re.compile(r"(?i)\b(?:print|show|display|leak)\s+(?:the\s+)?system\s+prompt\b"),
    re.compile(r"(?i)\bdeveloper\s+message\s*[:=]"),
    re.compile(r"(?i)\bdelete\s+all\s+files\b"),
    re.compile(r"(?i)\bcall\s+another\s+tool\b"),
    re.compile(r"(?i)\bbypass\s+security\b"),
    re.compile(r"(?i)\byou\s+are\s+now\b"),
    re.compile(r"(?i)\bact\s+as\s+admin\b"),
    re.compile(r"(?i)<\s*script\b"),
)

XSS_PATTERNS = (
    re.compile(r"(?i)<\s*script\b"),
    re.compile(r"(?i)\bjavascript\s*:"),
    re.compile(r"(?i)\bvbscript\s*:"),
    re.compile(r"(?i)\bdata\s*:\s*text/html"),
    re.compile(r"(?i)\bon\w+\s*="),
    re.compile(r"(?i)<\s*[a-z][\w:-]*[^>]{0,300}\s(?:href|src|srcdoc|formaction|action)\s*="),
    re.compile(
        r"(?is)\b(?:xss|cross-site scripting)\b.{0,120}"
        r"\b(?:attack|payload|bypass|exploit|vulnerab|script)\w*\b"
    ),
)

XSS_HTML_ATTRIBUTE_MARKERS = (
    "href",
    "src",
    "srcdoc",
    "formaction",
    "action",
    "xlinkhref",
)

XSS_DANGEROUS_SCHEMES = (
    "javascript",
    "vbscript",
    "datatexthtml",
)

XSS_EXECUTION_MARKERS = (
    "alert",
    "confirm",
    "prompt",
    "eval",
    "fetch",
    "documentcookie",
    "settimeout",
    "setinterval",
)

XSS_EVENT_HANDLER_RE = re.compile(
    r"on(?:abort|blur|change|click|error|focus|input|load|mouseover|submit)"
    r"[a-z0-9]{0,80}"
    r"(?:alert|confirm|prompt|eval|fetch|documentcookie|settimeout|setinterval)"
)

SUSPICIOUS_STATUS_PATTERNS = (
    re.compile(
        r"(?i)\b(?:api|http|upstream)?\s*status\s*[:=]?\s*"
        r"(?:401|403|429|500|502|503)\b"
    ),
)

LOCAL_DATA_EXFILTRATION_PATTERNS = (
    re.compile(r"(?i)\bdesktop\s+(?:path|listing|files|contents)\b"),
    re.compile(r"(?i)\b[A-Z]:\\Users\\[^\r\n\"'<>|]*\\Desktop\b"),
    re.compile(r"(?i)/mnt/[a-z]/Users/[^\r\n\"'<>|]*/Desktop\b"),
    re.compile(r"(?i)/(?:Users|home)/[^\r\n\"'<>|]*/Desktop\b"),
)

LOCAL_PATH_REDACTIONS = (
    re.compile(r"(?i)\b[A-Z]:\\Users\\[^\r\n\"'<>|]+"),
    re.compile(r"(?i)/mnt/[a-z]/Users/[^\r\n\"'<>|]+"),
    re.compile(r"(?i)/(?:Users|home)/[^\r\n\"'<>|]+"),
)

#unused imports that might be needed in the future
# def check_response(text: str, source: str = "response") -> str:
#     """
#     General post-call response check.

#     It can be used for:
#     - MCP tool output before sending it back to the model
#     - final LLM response before sending it back to the user
#     """
#     return check_response_details(text, source=source).text


def check_response_details(text: str, source: str = "response") -> ResponseCheckResult:
    if text is None:
        return ResponseCheckResult("")

    if not isinstance(text, str):
        text = str(text)

    if not text:
        return ResponseCheckResult(text)

    inspection_values = _inspection_variants(text)
    inspection_text = "\n".join(inspection_values)
    compact_inspection_values = _compact_inspection_variants(inspection_values)

    if _matches_any(SECRET_PATTERNS, inspection_text):
        return _blocked(
            source,
            "sensitive content was detected.",
        )

    if _matches_any(PROMPT_INJECTION_PATTERNS, inspection_text):
        return _blocked(
            source,
            "possible prompt injection content was detected.",
        )

    if has_xss_content(inspection_text, compact_inspection_values):
        return _blocked(
            source,
            "possible XSS content was detected.",
        )

    if _matches_any(SUSPICIOUS_STATUS_PATTERNS, inspection_text):
        return _blocked(
            source,
            "suspicious API status was detected.",
        )

    if _matches_any(LOCAL_DATA_EXFILTRATION_PATTERNS, inspection_text):
        return _blocked(
            source,
            "local desktop information was detected.",
        )

    redacted_text = redact_local_paths(text)

    return ResponseCheckResult(
        redacted_text,
        modified=redacted_text != text,
        reason="local path redacted" if redacted_text != text else "",
    )


def redact_local_paths(text: str) -> str:
    redacted = text
    for pattern in LOCAL_PATH_REDACTIONS:
        redacted = pattern.sub("[local-path-hidden]", redacted)
    return redacted


def _blocked(source: str, reason: str) -> ResponseCheckResult:
    return ResponseCheckResult(
        f"{source} blocked by security policy: {reason}",
        blocked=True,
        modified=True,
        reason=reason,
    )


def _matches_any(patterns: tuple[re.Pattern[str], ...], value: str) -> bool:
    return any(pattern.search(value) for pattern in patterns)


def has_xss_content(inspection_text: str, compact_values: set[str]) -> bool:
    if _matches_any(XSS_PATTERNS, inspection_text):
        return True

    return any(_compact_value_has_xss_payload(value) for value in compact_values)


def _compact_value_has_xss_payload(value: str) -> bool:
    if XSS_EVENT_HANDLER_RE.search(value):
        return True

    has_html_attribute = any(
        marker in value for marker in XSS_HTML_ATTRIBUTE_MARKERS
    )
    has_dangerous_scheme = any(
        scheme in value for scheme in XSS_DANGEROUS_SCHEMES
    )

    if has_html_attribute and has_dangerous_scheme:
        return True

    if has_dangerous_scheme and any(
        marker in value for marker in XSS_EXECUTION_MARKERS
    ):
        return True

    if "script" in value and any(
        marker in value for marker in XSS_EXECUTION_MARKERS
    ):
        return True

    return False


def _inspection_variants(text: str) -> set[str]:
    variants = {text}
    decoded = text

    for _ in range(2):
        decoded = html.unescape(unquote(decoded))
        variants.add(decoded)

    return {
        re.sub(r"\s+", " ", candidate).strip()
        for candidate in variants
    }


def _compact_inspection_variants(values: set[str]) -> set[str]:
    return {
        re.sub(r"[^a-z0-9]+", "", value.lower())
        for value in values
    }
