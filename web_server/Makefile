VENV = venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip
UVICORN = $(VENV)/bin/uvicorn

.PHONY: install mcp web all

# Dependencies installed by this prototype:
# fastapi: web framework for routes, form fields, and file upload endpoints.
# uvicorn: ASGI server used to run the FastAPI app locally.
# jinja2: template engine for rendering pages/home.html.
# pydantic: request/body validation models.
# python-dotenv: loads local secrets and configuration from .env.
# openai: OpenAI-compatible client for OpenRouter and local Ollama calls.
# fastmcp: MCP server/client framework for tool servers and host calls.
# httpx: async HTTP client used by API-backed MCP tools.
# sqlalchemy: local SQLite database ORM/session layer.
# authlib: GitHub OAuth login client.
# itsdangerous: signed session support required by Starlette sessions.
# PyJWT: internal JWT creation and verification between FastAPI and MCP.
# pypdf: PDF text extraction for uploaded PDF summarisation.
# python-multipart: multipart parser required by FastAPI Form/File uploads.
install:
	python3 -m venv $(VENV)
	$(PIP) install fastapi uvicorn jinja2 pydantic python-dotenv openai fastmcp httpx sqlalchemy authlib itsdangerous PyJWT pypdf python-multipart
mcp:
	$(PYTHON) main_mcp.py

web:
	$(UVICORN) main:app --host 0.0.0.0 --port 8000 --reload
session-key:
	$(PYTHON) -c "import secrets; print(secrets.token_urlsafe(32))"
all:
	@echo "Run these in separate terminals:"
	@echo "make mcp"
	@echo "make web"
