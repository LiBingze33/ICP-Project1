VENV = venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip
UVICORN = $(VENV)/bin/uvicorn

.PHONY: install mcp web all

install:
	python3 -m venv $(VENV)
	$(PIP) install fastapi uvicorn jinja2 pydantic python-dotenv openai fastmcp httpx sqlalchemy cryptography "py-key-value-aio[disk]" diskcache

# NEW: only run the parent MCP server
mcp:
	$(PYTHON) main_mcp.py

web:
	$(UVICORN) main:app --reload --port 8000

all:
	@echo "Run these in separate terminals:"
	@echo "make mcp"
	@echo "make web"