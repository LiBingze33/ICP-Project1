import json
import os

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from openai import OpenAI

load_dotenv()

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



async def run_agent(user_message: str, user_id: str) -> str:
    #connect to the MCP server at MCP_URL
    #send the user identity in the header
    transport = StreamableHttpTransport(
        url=MCP_URL,
        headers={
            "X-User-Id": user_id,
        },
    )
    #Open the MCP clint cconnection
    async with Client(transport) as mcp_client:
        # Now the backendd can actuallyy talk to the MCP server
        # 1. Get prompt from MCP server
        prompt_result = await mcp_client.get_prompt("bing_weather_style")
        #build the initial messages list
        messages = []
        for m in prompt_result.messages:
            text = getattr(m.content, "text", None)
            if text:
                messages.append({"role": m.role, "content": text})
            # After this, the messages might look like this
            #             [
            #     {
            #         "role": "system",
            #         "content": "When presenting any result from the weather server..."
            #     }
            # ]
        # 2. Add user message
        messages.append({"role": "user", "content": user_message})
            #After this, the mesage become something like this 
            #         [
            #     {
            #         "role": "system",
            #         "content": "When presenting any result from the weather server..."
            #     },
            #     {
            #         "role": "user",
            #         "content": "what is my saved weather preference?"
            #     }
            # ]

        # 3. Get available tools from MCP server
        tools_result = await mcp_client.list_tools()

        available_tools = []
        for tool in tools_result:
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
        #Model will be able to see the prompt, the user question and the list of available tools
        first = llm_client.chat.completions.create(
            model="anthropic/claude-3.5-sonnet",
            messages=messages,
            tools=available_tools,
            max_tokens=300,

        )
        #Now the backend check what the model said and there will be two possibility
        msg = first.choices[0].message

        final_parts = []
        #the msg.content contains the answer, no tool calls
        if msg.content:
            final_parts.append(msg.content)

        # 5. If tool calls exist, execute them
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
            #This could be important to add in the report, even if the model ask for a weird tool, only these three are allowed
            allowed_tools = {
                "get_alerts",
                "get_forecast",
                "get_saved_weather_preferences",
            }
            for tc in msg.tool_calls:
                #get tool name
                tool_name = tc.function.name
            #BLOCK not allowed tools
                if tool_name not in allowed_tools:
                    raise ValueError(f"Tool not allowed: {tool_name}")
            #parse the tool arguments
                tool_args = json.loads(tc.function.arguments or "{}")
            #if the model requested
            # {"state":"CA"} -> {"state":"CA"}
                # validate input
                if tool_name == "get_alerts":
                    state = tool_args.get("state", "")
                    if not isinstance(state, str) or len(state) != 2:
                        raise ValueError("Invalid state code.")

                if tool_name == "get_forecast":
                    lat = tool_args.get("latitude")
                    lon = tool_args.get("longitude")
                    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                        raise ValueError("Invalid coordinates.")
                #call the MCP tool, backend really ask the MCP server to execute the tool
                tool_result = await mcp_client.call_tool(tool_name, tool_args)
                #convert the tool result into plain text
                tool_text = extract_tool_text(tool_result)
                #Now the conversation contains
                #system prompt
                #user message
                #assistant tool request
                #tool result
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_text,
                    }
                )
                #now the model can see : the tool result is Los Angeles, CA
            # 6. Second LLM call with tool results
            #Now the model will have the tool result
            #The first model could not answer fully, as the tool had not run yet
            #things like here is the tooloutput, turn into a final user-facing answer
            second = llm_client.chat.completions.create(
                model="anthropic/claude-3.5-sonnet",
                messages=messages,
                tools=available_tools,
                max_tokens=300,

            )

            if second.choices[0].message.content:
                final_parts.append(second.choices[0].message.content)

        return "\n".join(part for part in final_parts if part).strip()