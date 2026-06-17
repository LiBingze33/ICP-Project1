# Secure AI MCP Web Server

This project is a security-focused prototype for exploring how an AI web
application can safely use external tools, online APIs, and Model Context
Protocol (MCP) servers. The system is designed to keep the language model useful
while placing security checks around tool selection, tool arguments, uploaded
content, tool output, and final model responses.

The prototype demonstrates layered controls for:

- authentication and role-aware tool access
- MCP tool allowlisting
- private user workspaces
- pre-call validation before tools run
- post-call output scanning after tools or APIs return data
- audit logging for tool execution decisions
- uploaded file and image summarisation with security checks

## Project Purpose

The project is security-first rather than product-first. It supports a capstone
report by demonstrating how LLM-powered applications can interact with local
files, online APIs, and MCP tools without giving the model unrestricted access to
system resources.

The main security idea is that every useful action passes through controlled
layers:

```text
User request
-> FastAPI web app
-> authentication and database user lookup
-> MCP host policy selection
-> tool allowlist and argument validation
-> MCP tool or API call
-> post-call response check
-> audit log
-> final response check
-> browser response
```

## Current Features

### Web App and Authentication

- FastAPI web chat interface
- GitHub OAuth login
- Local user records stored with SQLAlchemy
- Per-user private workspace folders
- Trusted user context loaded from the database, not directly from the session

### MCP Tool Integration

- Parent MCP server mounted at `http://127.0.0.1:9000/mcp`
- Weather MCP tools for online weather API demonstrations
- Local file MCP tools for listing, reading, creating, and deleting files
- Admin MCP tool example for role-based access
- Security demo MCP tools for safe post-call testing
- Tool allowlisting in `services/mcp_host.py`

### Pre-Call Security

Pre-call checks happen before a tool is executed or before uploaded text is sent
to the model.

Controls include:

- filename validation
- path traversal blocking
- workspace restriction
- sensitive filename blocking, such as `.env` and private key files
- XSS input detection
- SQL injection input detection
- delete confirmation for risky file operations
- file upload extension allowlisting

### Post-Call Security

Post-call checks happen after a tool, API, uploaded-content extraction, or model
response has produced output.

The response checker can:

- block secret-like content, API keys, bearer tokens, JWTs, and private keys
- block prompt injection text
- block suspicious API status output, such as `403`, `429`, or `500`
- block local Desktop information leakage
- redact local machine paths
- block XSS-like content in tool output or final model summaries

Post-call checking is implemented in:

```text
web_server/middleware/response_check.py
```

MCP tool calls are wrapped and checked in:

```text
web_server/services/mcp_host.py
```

### Canonicalisation-Based XSS Detection

The XSS detector does not only match one hard-coded payload. It first
canonicalises output by:

- decoding URL encoding, such as `%0a` and `%09`
- decoding HTML entities, such as `&#x0A;`
- normalising whitespace
- compacting text by removing separators and punctuation
- checking for dangerous structure

This helps detect variants such as:

```text
j%0aavas%09cript
java&#x0A;script
j a v a s c r i p t
<img src=x onerror=alert(1)>
```

The detector looks for combinations such as:

- HTML attributes like `href`, `src`, `action`, or `formaction`
- dangerous schemes like `javascript`, `vbscript`, or `data:text/html`
- execution markers like `alert`, `confirm`, `prompt`, `eval`, or `fetch`
- event handlers like `onerror`, `onclick`, or `onload`

### Uploaded File and Image Summarisation

The web app supports uploaded content for summarisation or description:

- `.txt`
- `.md`
- `.pdf`
- `.png`
- `.jpg`
- `.jpeg`

Text and Markdown files are decoded as UTF-8.

PDF files are extracted with `pypdf` or `PyPDF2` if available. Extracted PDF text
is scanned before it is sent to the model.

Images are sent to a vision-capable model for description. The final image
description is scanned by the post-call checker before it is shown to the user.

Important limitation: image text is currently checked after the model describes
the image. A stronger future layer would add OCR before the image is sent to the
model.

### Security Demo MCP Tools

The demo MCP server provides safe test tools that simulate suspicious API
responses without reading real secrets or real Desktop files.

Demo tools include:

- `demo_safe_health_check`
- `demo_safe_public_info`
- `demo_safe_echo`
- `demo_fake_secret_api`
- `demo_fake_desktop_info_api`
- `demo_fake_error_status_api`

These tools are useful for showing post-call blocking and audit logging in a
controlled way.

### Post-Call Audit Logging

Tool execution decisions are logged to:

```text
web_server/security/post_call_audit.log
```

Audit records include:

- timestamp
- tool name
- user identity
- role
- status
- duration
- output size
- decision: `allowed`, `modified`, `blocked`, or `error`
- block reason

Sensitive audit fields such as tokens, secrets, content, and workspace paths are
redacted before writing the log.

## Requirements

- Python 3.10 or above
- pip
- virtual environment support
- OpenRouter API key
- GitHub OAuth credentials
- `pypdf` for PDF summarisation

## Installation

From the `web_server` directory:

```bash
python3 -m venv venv
source venv/bin/activate
make install
```

Create or update `.env`:

```env
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
OPENROUTER_API_KEY=your_openrouter_api_key
SESSION_SECRET_KEY=your_session_secret
INTERNAL_JWT_SECRET=your_internal_jwt_secret
```

## How to Run

Start the MCP service:

```bash
cd "/mnt/c/Users/tuetm/MCP - ICT Project/ICP-Project1/web_server"
source venv/bin/activate
make mcp
```

In a second terminal, start the web app:

```bash
cd "/mnt/c/Users/tuetm/MCP - ICT Project/ICP-Project1/web_server"
source venv/bin/activate
make web
```

Open:

```text
http://127.0.0.1:8000
```

## Example Web App Test Prompts

### File Tools

```text
Create a file named notes.txt with content hello world
```

```text
Read the file notes.txt
```

```text
Read the file ../../secret.txt
```

Expected: blocked for path traversal.

```text
Create a file named xss.txt with content <script>alert(1)</script>
```

Expected: blocked before file creation.

### Uploaded File Summarisation

Upload a normal `.txt` file and ask:

```text
Summarise this uploaded file
```

Expected: allowed and summarised.

Upload a `.txt` file containing:

```text
OPENROUTER_API_KEY=sk-test-secret
```

Then ask:

```text
Summarise this uploaded file
```

Expected: blocked before summarisation.

Upload a PDF and ask:

```text
Summarise this uploaded PDF
```

Expected: extracted, scanned, and summarised if safe.

Upload an image and ask:

```text
Describe this uploaded image
```

Expected: described if the final model output passes the post-call checker.

### Post-Call Demo API Tools

```text
Run the security demo safe health check
```

Expected: allowed.

```text
Call the fake secret API for a post-call demo
```

Expected: blocked by post-call secret detection.

```text
Call the fake desktop info API for a post-call demo
```

Expected: blocked by post-call local data leakage detection.

```text
Call the fake error status API for a post-call demo
```

Expected: blocked by suspicious API status detection.

## Running Tests

From `web_server`:

```bash
source venv/bin/activate
python3 -B -m unittest tests.test_postcall_security -v
python3 -B -m unittest tests.test_upload_processing -v
python3 -B -m unittest tests.test_post_call_audit -v
```

## Project Structure

```text
web_server/
  database/
    db.py
    model.py
  mcp_servers/
    admin_server.py
    demo_security_server.py
    local_file_server.py
    weather_http_server.py
  middleware/
    internal_jwt.py
    pre_check.py
    response_check.py
  pages/
    home.html
  security/
    post_call_audit.py
  services/
    mcp_host.py
    upload_processing.py
  tests/
    test_post_call_audit.py
    test_postcall_security.py
    test_upload_processing.py
  main.py
  main_mcp.py
  Makefile
```

## Security Notes

This is a prototype for demonstrating MCP security concepts. It is not
production-ready security software.
Production hardening would require:

- stronger structured logging and monitoring
- stricter file type validation
- OCR scanning before image-to-model calls
- malware scanning for uploaded files
- formal threat modelling
- broader fuzz testing for prompt injection and XSS variants
- secure deployment and secret management

## Important Files to Exclude from GitHub

Make sure these are included in `.gitignore`:

```gitignore
.env
venv/
__pycache__/
*.pyc
database.db
security/post_call_audit.log
user_workspaces/
```
