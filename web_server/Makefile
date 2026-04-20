VENV = venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip
UVICORN = $(VENV)/bin/uvicorn

.PHONY: install mcp web docker-build-web docker-run-web docker-build-mcp docker-run-mcp docker-run-all

install:
	python3 -m venv $(VENV)
	$(PIP) install fastapi uvicorn jinja2 pydantic python-dotenv openai fastmcp httpx sqlalchemy cryptography "py-key-value-aio[disk]" diskcache

mcp:
	$(PYTHON) main_mcp.py

web:
	$(UVICORN) main:app --reload --host 0.0.0.0 --port 8000

build-web:
	docker build -t icp-web -f Dockerfile.web .

run-web:
	docker run --env-file .env -p 8000:8000 icp-web

build-mcp:
	docker build -t icp-mcp -f Dockerfile.mcp .

run-mcp:
	docker run --env-file .env -p 9000:9000 icp-mcp

docker-run-all:
	@echo "Run these in separate terminals:"
	@echo "make docker-run-mcp"
	@echo "make docker-run-web"