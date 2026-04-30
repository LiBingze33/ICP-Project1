def check_tool_response(tool_name: str, tool_text: str) -> str:
    # Check MCP tool output before it is sent back to the model

    sensitive_keywords = [
        "api_key",
        "secret",
        "password",
        "token",
        "client_secret",
        "OPENROUTER_API_KEY",
        "GITHUB_CLIENT_SECRET",
        "OAUTH_STORAGE_ENCRYPTION_KEY",
    ]

    prompt_injection_phrases = [
        "ignore previous instructions",
        "ignore all previous instructions",
        "reveal your system prompt",
        "delete all files",
        "call another tool",
        "bypass security",
    ]

    lower_text = tool_text.lower()

    for keyword in sensitive_keywords:
        if keyword.lower() in lower_text:
            return (
                "Response blocked by security policy: "
                "sensitive content was detected in the tool output."
            )

    for phrase in prompt_injection_phrases:
        if phrase in lower_text:
            return (
                "Response blocked by security policy: "
                "possible prompt injection content was detected in the tool output."
            )

    if "/Users/" in tool_text:
        tool_text = tool_text.replace("/Users/", "[local-path-hidden]/")

    return tool_text