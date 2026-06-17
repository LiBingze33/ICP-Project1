# Secure AI MCP Web Server

This project is a security-focused prototype for exploring how an MCP-based web application can safely use external tools, and online APIs. The system is using layered security architecture to keep the language model useful and safe around tool selection, tool arguments, uploaded content, tool output, and final model responses.

The prototype will include the following functions:

- OAuth Authentication and role-based tool access
- MCP tool allow-list, policy checks
- Private user workspaces
- Pre-call validation before tools run
- Post-call output scanning after tools or APIs return data
- Audit logging for tool execution decisions
- Uploaded file and image summarisation with security checks

## Project Purpose
The main purpose of the product is to prioritise the security features for the MCP-based model rather than implementing powerful AIs. The prototype will demonstrate how LLM applications can interact with local files, external APIs and MCP tools with a limited access based on the configured security rules. The idea is that every action must pass through security controll layers:

The logical flow is shown below:

OAuth authentication via Github --> database user lookup and limit accesses within assigned roles --> User makes request in the web app interface --> pre_call_check: policy matching, allowed tool list, sanitzation, canonicalise --> MCP Tool/API --> post_call_check: detect patters, canonicalise, audit log,.. --> LLM-based interface response

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
- Imported MCP tools for listing, reading, creating, and deleting files
- Role-based access
- Security demo MCP tools for safe post-call testing
- Tool allowlisting in `services/mcp_host.py`

### Pre-Call Security

Pre-call checks happen before a tool is executed or before uploaded text is sent to the model.
Pre-call checks are implemented inside: web_server/middleware/pre_check.py

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
Post-call checking is implemented in:web_server/middleware/response_check.py
MCP tool calls are wrapped and checked in: web_server/services/mcp_host.py

The response checker can:

- block secret-like content, API keys, bearer tokens, JWTs, and private keys
- block prompt injection text
- block suspicious API status output, such as `403`, `429`, or `500`
- block XSS, SQLi and indirect/direct prompt injection content in tool output or returned content

Canonicalisation-Based XSS Detection: The XSS detector does not only match one hard-coded payload. It first canonicalises output by:

- decoding URL encoding, such as `%0a` and `%09`
- decoding HTML entities, such as `&#x0A;`
- normalising whitespace
- compacting text by removing separators and punctuation
- checking for dangerous structure

The detector looks for combinations such as:

- HTML attributes like `href`, `src`, `action`, or `formaction`
- dangerous schemes like `javascript`, `vbscript`, or `data:text/html`
- execution markers like `alert`, `confirm`, `prompt`, `eval`, or `fetch`
- event handlers like `onerror`, `onclick`, or `onload`

Uploaded File and Image Summarisation: The web app supports uploaded content for summarisation or description. The tool is implemented as a way to create for scenarios for web-based tests to check whether the security features are working or not.

Text and Markdown files are decoded as UTF-8.

PDF handling is supported by using `pypdf` or `PyPDF2`. Extracted PDF text is scanned before it is sent to the model.

Images are sent to a vision-capable model for description. The final image description is scanned by the post-call checker before it is shown to the user.

Important limitation: image text is currently checked after the model describes
the image. A stronger future layer would add OCR before the image is sent to the
model.

### Security Demo MCP Tools

The demo MCP server provides safe test tools that simulate suspicious API responses without reading real secrets or real Desktop files.

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

This function is triggered when considering external API calls to check if the API is safe to use. Tool execution decisions are logged to:
web_server/security/post_call_audit.log

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
Open the following URL in any browser: http://127.0.0.1:8000

## Example Web App Test Prompts

### File Tools

```text
Create a file named notes.txt with content hello world
```

```text
Read the file ../../secret.txt --> Expected: blocked for path traversal.
```

```text
Create a file named xss.txt with content <script>alert(1)</script> --> Expected: blocked before file creation.
```

### Uploaded File Summarisation

Upload a normal `.txt` file and ask:

```text
Summarise this uploaded file --> Expected: allowed and summarised.
```

Upload a `.txt` file containing the following text and ask to summerise the content --> Expected: blocked before summarisation.

```text
OPENROUTER_API_KEY=sk-test-secret
```

Upload a PDF/image and ask either describe the image or summarise the content --> Expected: described if the final model output passes the post-call checker.

### Post-Call Demo API Tools

```text
Run the security demo safe health check --> Expected: allowed.
``
```text
Call the fake secret API for a post-call demo --> Expected: blocked by post-call secret detection.
```

```text
Call the fake desktop info API for a post-call demo --> Expected: blocked by post-call local data leakage detection.
```


## Project Structure

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
  main.py
  main_mcp.py
  Makefile


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
