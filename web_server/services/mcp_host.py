import json
import os

from dotenv import load_dotenv
from fastmcp import Client
from openai import OpenAI

load_dotenv()

# MCP is called internally by FastAPI after the user has logged in.
# For VM deployment, keep this as 127.0.0.1 because MCP runs on the same VM.
MCP_URL = "http://127.0.0.1:9000/mcp"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")

ollama_client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama",
)

openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)


def extract_tool_text(tool_result) -> str:
    if isinstance(tool_result, str):
        return tool_result

    content = getattr(tool_result, "content", None)
    if content is not None:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(getattr(item, "text", str(item)) for item in content)
        return str(content)

    return getattr(tool_result, "text", str(tool_result))


def choose_context(user_message: str) -> tuple[str, set[str]]:
    text = user_message.lower()

    if "file" in text or "read" in text or ".txt" in text or ".md" in text:
        return "files_file_style", {
            "files_list_files",
            "files_read_file",
            "files_create_file",
            "files_delete_file",
        }

    return "weather_bing_weather_style", {
        "weather_get_alerts",
        "weather_get_forecast",
        "weather_get_user_info",
        "weather_only_tool",
    }


def filter_tools_by_user_role(allowed_tools: set[str], user: dict) -> set[str]:
    """
    Simple role-based authorization layer.

    Default GitHub login creates a normal user.
    Normal users should not be able to create/delete files.
    Admins can use all tools in the selected context.
    """
    role = user.get("role", "user")

    if role == "users":
        return allowed_tools

    # Normal users cannot modify files
    restricted_tools = {
        # "files_create_file",
        "files_delete_file",
    }

    return allowed_tools - restricted_tools


def call_llm(messages, available_tools, backend="openrouter", max_tokens=500):
    backend = backend.lower()

    if backend == "openrouter":
        client = openrouter_client
        model = OPENROUTER_MODEL

    elif backend == "ollama":
        client = ollama_client
        model = OLLAMA_MODEL

    else:
        raise ValueError(
            f"Invalid backend '{backend}'. Use 'openrouter' or 'ollama'."
        )

    result = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=available_tools,
        max_tokens=max_tokens,
    )

    choice = result.choices[0]
    msg = choice.message

    print("\n===== LLM DEBUG START =====")
    print("BACKEND:", backend)
    print("MODEL:", model)
    print("MAX TOKENS:", max_tokens)
    print("FINISH REASON:", getattr(choice, "finish_reason", None))
    print("CONTENT REPR:", repr(msg.content or ""))
    print("CONTENT LENGTH:", len(msg.content or ""))
    print("TOOL CALLS:", repr(msg.tool_calls))
    print("USAGE:", getattr(result, "usage", None))
    print("===== LLM DEBUG END =====\n")

    return result

async def run_agent(user_message: str, user: dict,backend: str = "openrouter") -> str:
    """
    user comes from FastAPI session after GitHub OAuth login.

    Example:
    {
        "user_id": 1,
        "login": "github_username",
        "email": "...",
        "role": "user"
    }
    """
    github_login = user.get("login", "unknown_user")
    role = user.get("role", "user")

    prompt_name, allowed_tools = choose_context(user_message)

    # Apply authorization based on logged-in user's role
    allowed_tools = filter_tools_by_user_role(allowed_tools, user)

    # No FastMCP OAuth here.
    # FastAPI already authenticated the user.
    # MCP is internal on 127.0.0.1.
    mcp_client_cm = Client(MCP_URL)

    async with mcp_client_cm as mcp_client:
        # 1. Get prompt from MCP server
        prompt_result = await mcp_client.get_prompt(prompt_name)

        # 2. Build messages
        messages = []
        for m in prompt_result.messages:
            text = getattr(m.content, "text", None)
            if text:
                messages.append({"role": m.role, "content": text})

        messages.append(
            {
                "role": "user",
                "content": (
                    f"Authenticated GitHub user: {github_login}\n"
                    f"User role: {role}\n\n"
                    f"User request: {user_message}"
                ),
            }
        )

        # 3. Get only allowed tools
        tools_result = await mcp_client.list_tools()

        available_tools = []
        for tool in tools_result:
            if tool.name in allowed_tools:
                available_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": tool.inputSchema,
                        },
                    }
                )

        # 4. First LLM call
        first = call_llm(
            messages=messages,
            available_tools=available_tools,
            backend=backend,
            max_tokens=500,
        )

        msg = first.choices[0].message
        final_parts = []

        if msg.content:
            final_parts.append(msg.content)

        # 5. Execute tool calls if any
        if msg.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )

            for tc in msg.tool_calls:
                tool_name = tc.function.name

                # Allowlist check
                if tool_name not in allowed_tools:
                    raise ValueError(f"Tool not allowed for this user: {tool_name}")

                # Parse arguments
                tool_args = json.loads(tc.function.arguments or "{}")

                # Input validation
                if tool_name == "weather_get_alerts":
                    state = tool_args.get("state", "")
                    if not isinstance(state, str) or len(state.strip()) != 2:
                        raise ValueError("Invalid state code.")

                if tool_name == "weather_get_forecast":
                    lat = tool_args.get("latitude")
                    lon = tool_args.get("longitude")

                    try:
                        lat = float(lat)
                        lon = float(lon)
                    except (TypeError, ValueError):
                        raise ValueError("Invalid coordinates.")

                    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                        raise ValueError("Coordinates out of range.")

                    tool_args["latitude"] = lat
                    tool_args["longitude"] = lon
                    
                if tool_name in {
                    "files_read_file",
                    "files_create_file",
                    "files_delete_file",
                }:
                    filename = tool_args.get("filename", "")
                    if not isinstance(filename, str) or not filename.strip():
                        raise ValueError("Invalid filename.")

                if tool_name == "files_create_file":
                    content = tool_args.get("content", "")
                    if not isinstance(content, str):
                        raise ValueError("Invalid file content.")
                # This makes sure file tools only use the current user's private folder.
                if tool_name in {
                    "files_list_files",
                    "files_read_file",
                    "files_create_file",
                    "files_delete_file",
                }:
                    workspace_path = user.get("workspace_path")

                    if not workspace_path:
                        raise ValueError("User workspace path was not found in session.")

                    tool_args["workspace_path"] = workspace_path
                # Call MCP tool internally
                tool_result = await mcp_client.call_tool(tool_name, tool_args)
                tool_text = extract_tool_text(tool_result)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_text,
                    }
                )

            # 6. Second LLM call with tool outputs
            second = call_llm(
                messages=messages,
                available_tools=available_tools,
                backend=backend,
                max_tokens=500,
            )

            if second.choices[0].message.content:
                final_parts.append(second.choices[0].message.content)

        return "\n".join(part for part in final_parts if part).strip()