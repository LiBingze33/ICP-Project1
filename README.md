# MCP Project — Original University Implementation

This branch preserves the original university project implementation from `main` at commit `612d676c8091f3d298a4e5f54b2caefe3c5f8412`. Its application files and history are retained; this README explains the original terminal client and basic web demonstration.

The original project introduced a terminal client that connects to a local weather MCP server, forming the starting point for the later authenticated web versions.

## Architecture and components

The repository contains two independent demonstrations:

```text
Terminal input -> MCP client -> OpenRouter model
                       |          |
                       +-- model-requested tools
                       |
                       +-- stdio MCP weather server -> US National Weather Service

Browser -> FastAPI /chat -> OpenRouter model
                     |
                     +-- HTTP weather MCP :9000 OR file MCP :9001
```

`Terminal/mcp-client/client.py` starts the supplied server script as a subprocess, discovers its tools and prompt, sends a query to OpenRouter, executes requested MCP tools, and makes a follow-up model call. The interactive command `quit` closes the client.

`Terminal/weather/weather.py` provides US state alerts, coordinate-based forecasts, a weather presentation prompt, and a saved-preference demonstration using a server-supplied demo identity.

The separate `web_server` demonstration serves a Jinja2 chat page. The host selects the file server when a request contains file-related keywords; otherwise it selects weather. It uses explicit tool allowlists and basic argument checks. Weather preferences are held in a hard-coded demonstration dictionary, not a real user database. File operations share `mcp_servers/demo_docs`.

## Project structure

```text
README.md
Terminal/
  mcp-client/
    client.py                  # Interactive OpenRouter/MCP client
    pyproject.toml, uv.lock     # Declared Python dependencies
  weather/
    weather.py                 # Actual stdio weather MCP server
    main.py                    # Greeting scaffold, not the MCP entry point
    test.py                    # Prints a greeting; not a functional test suite
    pyproject.toml, uv.lock
web_server/
  Makefile
  main.py                      # GET / and POST /chat
  services/mcp_host.py          # Server routing and model/tool orchestration
  pages/home.html
  mcp_servers/
    weather_http_server.py
    local_file_server.py
    demo_docs/
    secrets/                   # Existing demonstration path; not required config
fast_api_practice/fastapi_paractice/
  main.py                      # Independent introductory FastAPI example
  pyproject.toml, uv.lock
```

## Requirements and dependencies

Use Python 3.12 for the terminal projects, as specified by their version files and manifests; the independent FastAPI practice project specifies Python 3.13. You also need pip, virtual environment support, network access to OpenRouter, and an `OPENROUTER_API_KEY`. Live weather needs access to `api.weather.gov`.

The terminal client imports `openai`, `mcp`, and `python-dotenv`; the weather server imports `httpx` and `fastmcp`. The existing terminal manifests omit some of these runtime imports. The commands below install the actual imports without changing those manifests. The web Makefile installs FastAPI, Uvicorn, Jinja2, Pydantic, python-dotenv, OpenAI, FastMCP, and HTTPX.

## Run the terminal version

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install openai python-dotenv mcp httpx 'fastmcp==3.2.4'
cd Terminal/mcp-client
python -u client.py ../weather/weather.py
```

Before starting, supply `OPENROUTER_API_KEY` through the process environment or a private `.env` in `Terminal/mcp-client`. Never commit its value. FastMCP 3.2.4 is a compatibility choice for these APIs, not a version pinned by the original repository. Unpinned future dependency releases may behave differently.

Example queries from the original documentation:

- “What weather tools do you have?”
- “Are there any alerts in California?”
- “What is the forecast for a location?” Specify coordinates if requested.

Type `quit` to exit. Forecast coverage depends on the US National Weather Service. Model availability depends on OpenRouter; the code uses a fixed model identifier.

## Run the original web demonstration

From `web_server`, run `make install` and supply `OPENROUTER_API_KEY` in a private `.env` or the process environment. Start each command in a separate terminal, always from `web_server`:

```bash
make weather
```

```bash
make file
```

```bash
make web
```

Open `http://127.0.0.1:8000`. The two HTTP MCP endpoints are `http://127.0.0.1:9000/mcp` and `http://127.0.0.1:9001/mcp`. The web Makefile uses unpinned dependencies, so compatibility should be checked when selecting package versions.

## Security Scope & Future Improvements

This version is intended for local learning and demonstrations. Its security controls centre on explicit tool allowlists, basic argument validation, and a server-supplied demo identity. It uses shared demonstration files rather than authenticated user workspaces.

Authentication, per-user isolation, and layered output checks are developed in the later branches. Further work for this original version would include dependency compatibility testing and broader automated checks. Keep credentials and personal documents outside the demonstration resources.

## Project evolution

| Branch | Purpose |
| --- | --- |
| [terminal_required](https://github.com/LiBingze33/ICP-Project1/tree/terminal_required) | This original university implementation |
| [local_mcp](https://github.com/LiBingze33/ICP-Project1/tree/local_mcp) | Advanced local web system with authentication and layered checks |
| [domain_mcp](https://github.com/LiBingze33/ICP-Project1/tree/domain_mcp) | Advanced system configured for the public deployment |
| [main](https://github.com/LiBingze33/ICP-Project1/tree/main) | Primary portfolio presentation of the local implementation |

The public version is associated with [https://9163.syslab.au](https://9163.syslab.au). Its current availability is not established by this documentation.
