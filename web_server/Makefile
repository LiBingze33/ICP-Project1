VENV = venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip
UVICORN = $(VENV)/bin/uvicorn

.PHONY: install weather web all

install:
	python3 -m venv $(VENV)
	$(PIP) install fastapi uvicorn jinja2 pydantic python-dotenv openai fastmcp httpx

weather:
	$(PYTHON) mcp_servers/weather_http_server.py
file:
	$(PYTHON) mcp_servers/local_file_server.py

web:
	$(UVICORN) main:app --reload --port 8000

all:
	@echo "Run these in separate terminals:"
	@echo "make weather"
	@echo "make web"