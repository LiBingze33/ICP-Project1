# Secure AI MCP Web Server

This project is a prototype web application for exploring the secure use of AI models with external APIs and Model Context Protocol (MCP) servers. The project focuses on layered security controls such as authentication, authorization, controlled tool access, and safer interaction with local or remote resources.

The system includes:

- a web interface for user interaction
- a main MCP controller
- multiple MCP servers for different tasks
- a database layer for local user and role handling
- middleware for authentication and authorization checks

## Project Purpose

This project is security-first rather than product-first. Its purpose is to explore how an AI-enabled system can safely interact with APIs, MCP servers, and tools without allowing unsafe actions, prompt bypass, privilege abuse, or unauthorized access.

The prototype supports the broader project goal of demonstrating a secure architecture for AI systems, where the main deliverable is a report and the software acts as a supporting proof of concept.

## Features

- Web-based chat interface
- MCP-based tool integration
- Local database support with SQLAlchemy
- Authentication and authorization middleware
- OAuth token caching
- Support for multiple MCP servers such as:
  - weather server
  - local file server

## Requirements

- Python 3.10 or above
- pip
- virtual environment support
- OpenRouter API key configured locally
- OAuth credentials if OAuth-based login is enabled

## Installation

Create and activate the virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
make install
```

## API Key and Local Configuration

The API key is stored locally in the development environment rather than hardcoded into the project files.

For example, it can be loaded from your local shell configuration:

```bash
source ~/.zshrc
```

If needed, other local credentials such as OAuth client details should also be stored securely in the local environment and not committed to GitHub.

## Project Structure

```text
web_server/
├── database/
│   ├── db.py
│   └── model.py
├── demo_docs/
├── mcp_servers/
│   ├── demo_docs/
│   ├── secrets/
│   ├── local_file_server.py
│   └── weather_http_server.py
├── middleware/
│   ├── __init__.py
│   └── auth.py
├── oauth_tokens/
│   ├── cache.db
│   ├── cache.db-shm
│   └── cache.db-wal
├── pages/
│   └── home.html
├── services/
│   └── mcp_host.py
├── venv/
├── database.db
├── main.py
├── main_mcp.py
├── Makefile
├── .gitignore
└── README.md
```

## Main Components

### `main.py`
Starts the FastAPI web application and serves the main interface.

### `main_mcp.py`
Runs the parent MCP process that coordinates MCP-related functionality.

### `mcp_servers/`
Contains the individual MCP servers.

- `weather_http_server.py` handles weather-related MCP requests
- `local_file_server.py` handles local file access for demonstration purposes

### `database/`
Contains the database setup and models.

- `db.py` configures the SQLAlchemy engine and session
- `model.py` defines the database tables

### `middleware/`
Contains authentication and authorization logic.

### `services/mcp_host.py`
Handles communication between the web application and MCP services.

### `pages/home.html`
Frontend HTML page for the web interface.

## How to Run

Start the MCP service:

```bash
make mcp
```

In a separate terminal, start the web server:

```bash
make web
```

Then open the application in your browser:

```text
http://127.0.0.1:8000
```

## Makefile Commands

### Install dependencies

```bash
make install
```

### Run MCP service

```bash
make mcp
```

### Run web server

```bash
make web
```

### Show startup instructions

```bash
make all
```

## Current Makefile

```makefile
VENV = venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip
UVICORN = $(VENV)/bin/uvicorn

.PHONY: install mcp web all

install:
	python3 -m venv $(VENV)
	$(PIP) install fastapi uvicorn jinja2 pydantic python-dotenv openai fastmcp httpx sqlalchemy cryptography "py-key-value-aio[disk]" diskcache

mcp:
	$(PYTHON) main_mcp.py

web:
	$(UVICORN) main:app --reload --port 8000

all:
	@echo "Run these in separate terminals:"
	@echo "make mcp"
	@echo "make web"
```

## Security Notes

This project is intended to demonstrate secure design ideas for AI systems that interact with tools and MCP servers. Depending on the implementation, security controls may include:

- user authentication
- authorization checks before tool execution
- restricted file access
- OAuth-based identity flow
- validation of tool requests and responses
- pre-tool and post-tool security checks

This is a prototype and should not be treated as production-ready security software.

## Important Files to Exclude from GitHub

Make sure these are included in `.gitignore`:

```gitignore
.env
venv/
__pycache__/
*.pyc
oauth_tokens/
database.db
cache.db
cache.db-shm
cache.db-wal
mcp_servers/secrets/
```

## Notes

- Keep API keys and OAuth secrets out of source control
- Use the local database and token cache only for development or demonstration unless properly secured
- Review all AI-assisted code before using it in the prototype
- The software prototype supports the report and is not the primary deliverable

##docker
docker build -t icp-web -f Dockerfile.web .
- docker build
	- tells Docker to create an image
- -t icp-web
	- gives the image a name: icp-web
- -f Dockerfile.web
	- tells Docker which Dockerfile recipe to use
- .
	- make current folder as the build text
