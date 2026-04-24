VENV = venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip
UVICORN = $(VENV)/bin/uvicorn

.PHONY: install mcp web all

install:
	python3 -m venv $(VENV)
	$(PIP) install fastapi uvicorn jinja2 pydantic python-dotenv openai fastmcp httpx sqlalchemy cryptography "py-key-value-aio[disk]" diskcache authlib itsdangerous
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
