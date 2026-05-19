def check_response(text: str, source: str = "response") -> str:
    """
    General response check.

    It can be used for:
    - MCP tool output before sending it back to the model
    - final LLM response before sending it back to the user
    """

    if not text:
        return text

    sensitive_keywords = [
        "api_key",
        "password",
        "token",
        "client_secret",
        "OPENROUTER_API_KEY",
        "GITHUB_CLIENT_SECRET",
        "OAUTH_STORAGE_ENCRYPTION_KEY",
        "INTERNAL_JWT_SECRET",
        "authorization",
        "bearer ",
    ]

    prompt_injection_phrases = [
        "ignore previous instructions",
        "ignore all previous instructions",
        "reveal your system prompt",
        "delete all files",
        "call another tool",
        "bypass security",
        "you are now",
        "act as admin",
    ]

    lower_text = text.lower()

    for keyword in sensitive_keywords:
        if keyword.lower() in lower_text:
            return (
                f"{source} blocked by security policy: "
                "sensitive content was detected."
            )

    for phrase in prompt_injection_phrases:
        if phrase.lower() in lower_text:
            return (
                f"{source} blocked by security policy: "
                "possible prompt injection content was detected."
            )

    # Hide local machine paths if they appear
    if "/Users/" in text:
        text = text.replace("/Users/", "[local-path-hidden]/")

    return text