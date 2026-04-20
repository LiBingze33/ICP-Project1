import json
import os

from dotenv import load_dotenv
from fastmcp import Client
from openai import OpenAI
from fastmcp.client.auth import OAuth
from key_value.aio.stores.disk import DiskStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from cryptography.fernet import Fernet

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

# llm_client = OpenAI(
#     base_url="https://openrouter.ai/api/v1",
#     api_key=os.getenv("OPENROUTER_API_KEY"),
# )
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")

ollama_client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama",  # required by client library, not really used by Ollama
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

def call_llm_with_fallback(messages, available_tools, max_tokens=1200):
    try:
        result = ollama_client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=messages,
            tools=available_tools,
            max_tokens=max_tokens,
        )

        choice = result.choices[0]
        msg = choice.message

        content = msg.content or ""
        tool_calls = msg.tool_calls

        print("\n===== OLLAMA DEBUG START =====")
        print("MODEL:", OLLAMA_MODEL)
        print("MAX TOKENS:", max_tokens)
        print("FINISH REASON:", getattr(choice, "finish_reason", None))
        print("CONTENT REPR:", repr(content))
        print("CONTENT LENGTH:", len(content))
        print("TOOL CALLS:", repr(tool_calls))
        print("USAGE:", getattr(result, "usage", None))

        # print the whole first choice if available
        try:
            print("RAW CHOICE:", choice.model_dump())
        except Exception:
            print("RAW CHOICE (str):", str(choice))

        print("===== OLLAMA DEBUG END =====\n")

        # return the result no matter what, so you can observe actual behavior
        return result

    except Exception as e:
        print("\n===== OLLAMA EXCEPTION =====")
        print(repr(e))
        print("===== FALLBACK TO OPENROUTER =====\n")

    return openrouter_client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=messages,
        tools=available_tools,
        max_tokens=150,
    )




async def run_agent(user_message: str) -> str:
    # user_id is kept for compatibility with your current route,
    # but OAuth now handles identity at the MCP server side.
    prompt_name, allowed_tools = choose_context(user_message)

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
        first = call_llm_with_fallback(
            messages=messages,
            available_tools=available_tools,
            max_tokens=1200,
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

                # Call MCP tool
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
            second = call_llm_with_fallback(
                messages=messages,
                available_tools=available_tools,
                max_tokens=1200,
            )

            if second.choices[0].message.content:
                final_parts.append(second.choices[0].message.content)

        return "\n".join(part for part in final_parts if part).strip()