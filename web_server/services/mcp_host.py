import json
import os
import re

from dotenv import load_dotenv
from fastmcp import Client
from openai import OpenAI
from fastmcp.client.auth import OAuth
from key_value.aio.stores.disk import DiskStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from cryptography.fernet import Fernet
from middleware.file_middleware import FileMiddleware

load_dotenv()

OAUTH_STORAGE_KEY = os.getenv("OAUTH_STORAGE_ENCRYPTION_KEY")
if not OAUTH_STORAGE_KEY:
    raise ValueError("Missing OAUTH_STORAGE_ENCRYPTION_KEY in environment.")

# Encrypted token storage for OAuth
encrypted_storage = FernetEncryptionWrapper(
    key_value=DiskStore(directory="./oauth_tokens"),
    fernet=Fernet(OAUTH_STORAGE_KEY),
)

oauth = OAuth(token_storage=encrypted_storage)

# One public parent MCP server only
MCP_URL = "http://127.0.0.1:9000/mcp"

llm_client = OpenAI(
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

    file_keywords = {
        "file",
        "read",
        "create",
        "delete",
        "remove",
        "list",
        "path",
        "show",
        "write",
    }

    if any(keyword in text for keyword in file_keywords) or ".txt" in text or ".md" in text:
        return "files_file_style", {
            "files_list_files",
            "files_list_user_files",
            "files_read_file",
            "files_create_file",
            "files_delete_file",
            "files_show_file_path",
        }

    return "weather_bing_weather_style", {
        "weather_get_alerts",
        "weather_get_forecast",
        "weather_get_user_info",
        "weather_only_tool",
    }


def is_file_action_request(user_message: str) -> bool:
    text = user_message.lower()
    return (
        any(keyword in text for keyword in ("create", "read", "delete", "list", "show", "see", "file"))
        or ".txt" in text
        or ".md" in text
    )


def has_explicit_delete_confirmation(user_message: str) -> bool:
    text = user_message.lower()
    return bool(
        re.search(r"\bconfirm\s*=?\s*true\b", text)
        or re.search(r"\bconfirmed\b", text)
    )


async def run_agent(user_message: str) -> str:
    # user_id is kept for compatibility with your current route,
    # but OAuth now handles identity at the MCP server side.
    prompt_name, allowed_tools = choose_context(user_message)

    # Block unsafe file payloads before the LLM can claim a file was created.
    if prompt_name == "files_file_style":
        FileMiddleware.reject_unsafe_text(user_message)

    mcp_client_cm = Client(MCP_URL, auth=oauth)

    async with mcp_client_cm as mcp_client:
        # 1. Get prompt from MCP server
        prompt_result = await mcp_client.get_prompt(prompt_name)

        # 2. Build messages
        messages = []
        for m in prompt_result.messages:
            text = getattr(m.content, "text", None)
            if text:
                messages.append({"role": m.role, "content": text})

        messages.append({"role": "user", "content": user_message})

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
        first = llm_client.chat.completions.create(
            model="anthropic/claude-sonnet-4.5",
            messages=messages,
            tools=available_tools,
            max_tokens=300,
        )

        msg = first.choices[0].message
        final_parts = []

        if msg.content:
            final_parts.append(msg.content)

        if prompt_name == "files_file_style" and is_file_action_request(user_message) and not msg.tool_calls:
            raise ValueError("File request was not executed because no file tool call was made.")

        # 5. Execute tool calls if any
        if msg.tool_calls:
            tool_outputs = []
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
                    raise ValueError(f"Tool not allowed: {tool_name}")

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
                    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                        raise ValueError("Invalid coordinates.")

                if tool_name in {
                    "files_list_user_files",
                    "files_read_file",
                    "files_create_file",
                    "files_delete_file",
                }:
                    if tool_name == "files_list_user_files":
                        username = tool_args.get("username", "")
                        if not isinstance(username, str) or not username.strip():
                            raise ValueError("Invalid username.")
                    else:
                        filename = tool_args.get("filename", "")
                        if not isinstance(filename, str) or not filename.strip():
                            raise ValueError("Invalid filename.")

                if tool_name == "files_create_file":
                    content = tool_args.get("content", "")
                    if not isinstance(content, str):
                        raise ValueError("Invalid file content.")

                if tool_name == "files_delete_file":
                    if not has_explicit_delete_confirmation(user_message):
                        raise ValueError(
                            "Delete requests must explicitly include 'confirm true'."
                        )
                    if tool_args.get("confirm") is not True:
                        raise ValueError(
                            "Delete tool call was rejected because confirm=True was not passed."
                        )

                # Call MCP tool
                tool_result = await mcp_client.call_tool(tool_name, tool_args)
                tool_text = extract_tool_text(tool_result)
                tool_outputs.append(tool_text)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_text,
                    }
                )

            # Return the exact file tool output to avoid LLM hallucinating success.
            if prompt_name == "files_file_style":
                return "\n".join(part for part in tool_outputs if part).strip()

            # 6. Second LLM call with tool outputs
            second = llm_client.chat.completions.create(
                model="anthropic/claude-sonnet-4.5",
                messages=messages,
                tools=available_tools,
                max_tokens=300,
            )

            if second.choices[0].message.content:
                final_parts.append(second.choices[0].message.content)

        return "\n".join(part for part in final_parts if part).strip()
