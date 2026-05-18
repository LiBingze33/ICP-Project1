import json
import os
import time
import jwt
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from fastmcp import Client
from openai import OpenAI
from fastmcp.client.transports import StreamableHttpTransport
load_dotenv()

TOOL_POLICIES = {
    "general": {
        "prompt": "general_style",
        "allowed_tools": set(),
    },
    "weather": {
        "prompt": "weather_bing_weather_style",
        "allowed_tools": {
            "weather_get_alerts",
            "weather_get_forecast",
            "weather_get_user_info",
        },
    },
    "files": {
        "prompt": "files_file_style",
        "allowed_tools": {
            "files_list_files",
            "files_read_file",
            "files_create_file",
            "files_delete_file",
        },
    },
}






# MCP is called internally by FastAPI after the user has logged in.
# For VM deployment, keep this as 127.0.0.1 because MCP runs on the same VM.
MCP_URL = "http://127.0.0.1:9000/mcp"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")
INTERNAL_JWT_SECRET = os.getenv("INTERNAL_JWT_SECRET")
if not INTERNAL_JWT_SECRET:
    raise RuntimeError("INTERNAL_JWT_SECRET is missing from .env")
ollama_client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama",
)

openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

def classify_context_with_ai(user_message: str, backend: str = "openrouter") -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "Classify the user's request into exactly one category: "
                "files, weather, or general. "
                "Return only one word. "
                "Use files if the user wants to list, read, create, write, delete, "
                "open, show, or summarise local files, folders, documents, notes, "
                "or workspace content. "
                "Use weather if the user asks about weather, forecast, temperature, "
                "rain, alerts, or location weather. "
                "Use general if no tool is needed."
            ),
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    result = call_llm(
        messages=messages,
        available_tools=[],
        backend=backend,
        max_tokens=10,
    )

    category = (result.choices[0].message.content or "").strip().lower()

    if category not in {"files", "weather", "general"}:
        return "general"

    return category

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


def choose_context(user_message: str, backend: str = "openrouter") -> tuple[str, set[str]]:
    category = classify_context_with_ai(user_message, backend=backend)

    if category not in TOOL_POLICIES:
        category = "general"
    #for now, file or weather
    policy = TOOL_POLICIES[category]

    return policy["prompt"], policy["allowed_tools"]

def filter_tools_by_user_role(allowed_tools: set[str], user: dict) -> set[str]:
    """
    Simple role-based authorization layer.

    Default GitHub login creates a normal user.
    Normal users should not be able to delete files.
    Admins can use all tools in the selected context.
    """
    role = user.get("role", "user")

    if role == "admin":
        return allowed_tools

    restricted_tools = {
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

    request_args = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }

    if available_tools:
        request_args["tools"] = available_tools

    result = client.chat.completions.create(**request_args)

    choice = result.choices[0]
    msg = choice.message

    print("\n===== LLM DEBUG START =====")
    print("BACKEND:", backend)
    print("MODEL:", model)
    print("MAX TOKENS:", max_tokens)
    print("AVAILABLE TOOLS:", [t["function"]["name"] for t in available_tools])
    print("FINISH REASON:", getattr(choice, "finish_reason", None))
    print("CONTENT REPR:", repr(msg.content or ""))
    print("CONTENT LENGTH:", len(msg.content or ""))
    print("TOOL CALLS:", repr(msg.tool_calls))
    print("USAGE:", getattr(result, "usage", None))
    print("===== LLM DEBUG END =====\n")

    return result


def create_internal_mcp_jwt(user: dict) -> str:
    """
    Create a short-lived JWT for backend-to-MCP communication.
    This token is only used between mcp_host.py and the MCP server.
    It should never be sent to the browser or the LLM.
    """
    now = int(time.time())

    payload = {
        # Who created this token
        "iss": "fastapi-web",

        # Who this token is intended for
        "aud": "mcp-server",

        # Internal service name
        "sub": "mcp-host",

        # User context for logging/auditing
        "user_id": str(user.get("user_id")),
        "github_login": user.get("login"),
        "role": user.get("role", "user"),

        # Token timing only valid for 60s
        "iat": now,
        "exp": now + 60,
    }

    return jwt.encode(payload, INTERNAL_JWT_SECRET, algorithm="HS256")


async def emit_log(emit, message: str):
    if emit:
        await emit(message)
        await asyncio.sleep(0.5)

async def run_agent(user_message: str, user: dict, backend: str = "openrouter", emit=None) -> str:
    """
    user comes from FastAPI session after GitHub OAuth login.
    """
    await emit_log(emit, "Agent started.")

    github_login = user.get("login", "unknown_user")
    role = user.get("role", "user")

    await emit_log(emit, f"Authenticated user loaded: {github_login}")
    await emit_log(emit, f"User role loaded: {role}")

    await emit_log(emit, "Classifying user request into policy category.")
    prompt_name, allowed_tools = choose_context(user_message, backend=backend)

    await emit_log(emit, f"Selected MCP prompt: {prompt_name}")
    await emit_log(emit, f"Tools allowed by selected policy: {sorted(list(allowed_tools))}")

    await emit_log(emit, "Applying role-based tool filtering.")
    allowed_tools = filter_tools_by_user_role(allowed_tools, user)

    await emit_log(emit, f"Tools allowed after role check: {sorted(list(allowed_tools))}")

    await emit_log(emit, "Creating internal JWT for FastAPI-to-MCP communication.")
    internal_jwt = create_internal_mcp_jwt(user)

    await emit_log(emit, "Creating MCP HTTP transport with internal authorization token.")
    transport = StreamableHttpTransport(
        MCP_URL,
        headers={
            "Authorization": f"Bearer {internal_jwt}",
        },
    )

    mcp_client_cm = Client(transport)

    await emit_log(emit, "Connecting to MCP server.")

    async with mcp_client_cm as mcp_client:
        await emit_log(emit, "MCP connection established.")

        # 1. Get prompt from MCP server
        await emit_log(emit, f"Loading MCP prompt: {prompt_name}")
        prompt_result = await mcp_client.get_prompt(prompt_name)
        await emit_log(emit, "MCP prompt loaded.")

        # 2. Build messages
        await emit_log(emit, "Building messages for the model.")
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

        await emit_log(emit, "Messages prepared.")

        # 3. Get only allowed tools
        await emit_log(emit, "Requesting available tools from MCP server.")
        tools_result = await mcp_client.list_tools()
        await emit_log(emit, f"MCP server returned {len(tools_result)} tools.")

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

        available_tool_names = [t["function"]["name"] for t in available_tools]
        await emit_log(emit, f"Tools exposed to model: {available_tool_names}")

        # 4. First LLM call
        await emit_log(emit, f"Calling LLM backend: {backend}")
        first = call_llm(
            messages=messages,
            available_tools=available_tools,
            backend=backend,
            max_tokens=500,
        )
        await emit_log(emit, "First LLM response received.")

        msg = first.choices[0].message
        final_parts = []

        if msg.content:
            await emit_log(emit, "LLM returned text content.")
            final_parts.append(msg.content)

        # 5. Execute tool calls if any
        if msg.tool_calls:
            await emit_log(emit, f"LLM requested {len(msg.tool_calls)} tool call(s).")

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

                await emit_log(emit, f"Tool requested by model: {tool_name}")
                await emit_log(emit, "Checking tool against allowlist.")

                # Allowlist check
                if tool_name not in allowed_tools:
                    await emit_log(emit, f"Tool blocked: {tool_name}")
                    raise ValueError(f"Tool not allowed for this user: {tool_name}")

                await emit_log(emit, f"Tool allowed: {tool_name}")

                # Parse arguments
                await emit_log(emit, "Parsing tool arguments.")
                tool_args = json.loads(tc.function.arguments or "{}")

                await emit_log(emit, f"Raw tool arguments: {tool_args}")

                # Input validation
                await emit_log(emit, "Running pre-tool input validation.")

                if tool_name == "weather_get_alerts":
                    state = tool_args.get("state", "")
                    if not isinstance(state, str) or len(state.strip()) != 2:
                        await emit_log(emit, "Validation failed: invalid state code.")
                        raise ValueError("Invalid state code.")

                if tool_name == "weather_get_forecast":
                    lat = tool_args.get("latitude")
                    lon = tool_args.get("longitude")

                    try:
                        lat = float(lat)
                        lon = float(lon)
                    except (TypeError, ValueError):
                        await emit_log(emit, "Validation failed: invalid coordinates.")
                        raise ValueError("Invalid coordinates.")

                    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                        await emit_log(emit, "Validation failed: coordinates out of range.")
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
                        await emit_log(emit, "Validation failed: invalid filename.")
                        raise ValueError("Invalid filename.")

                if tool_name == "files_create_file":
                    content = tool_args.get("content", "")
                    if not isinstance(content, str):
                        await emit_log(emit, "Validation failed: invalid file content.")
                        raise ValueError("Invalid file content.")

                if tool_name in {
                    "files_list_files",
                    "files_read_file",
                    "files_create_file",
                    "files_delete_file",
                }:
                    workspace_path = user.get("workspace_path")

                    if not workspace_path:
                        await emit_log(emit, "Validation failed: missing workspace path.")
                        raise ValueError("User workspace path was not found in session.")

                    tool_args["workspace_path"] = workspace_path
                    await emit_log(emit, f"Workspace path injected into tool arguments: /{Path(workspace_path).name}")
                await emit_log(emit, "Pre-tool validation passed.")
                await emit_log(emit, f"Calling MCP tool: {tool_name}")

                # Call MCP tool internally
                tool_result = await mcp_client.call_tool(tool_name, tool_args)

                await emit_log(emit, f"MCP tool finished: {tool_name}")

                tool_text = extract_tool_text(tool_result)
                await emit_log(emit, "Tool result extracted and prepared for model.")

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_text,
                    }
                )

            # 6. Second LLM call with tool outputs
            await emit_log(emit, "Calling LLM again with tool result.")
            second = call_llm(
                messages=messages,
                available_tools=available_tools,
                backend=backend,
                max_tokens=500,
            )
            await emit_log(emit, "Second LLM response received.")

            if second.choices[0].message.content:
                final_parts.append(second.choices[0].message.content)

        else:
            await emit_log(emit, "No tool call requested by the model.")

        await emit_log(emit, "Final response generated.")
        return "\n".join(part for part in final_parts if part).strip()