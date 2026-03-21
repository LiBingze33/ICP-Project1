# MCP Weather Client

This project is a simple MCP client that connects to a local weather server and allows users to interact with weather tools through the terminal.

## Requirements

- Python 3.10 or above
- pip
- An OpenRouter API key

## Installation

Create and activate a virtual environment:

python3 -m venv .venv
source .venv/bin/activate

Install the required modules:

pip install openai python-dotenv mcp httpx

## Environment Variables

Create a `.env` file in the `mcp-client` folder and add the following line:

OPENROUTER_API_KEY=your_api_key_here


## Project Structure

ICP1/
├── mcp-client/
│   ├── client.py
│   ├── README.md
│   └── .env
└── weather/
    └── weather.py

## How to Run

From inside the `mcp-client` folder, run:

python -u client.py ../weather/weather.py

## Example Usage

After running the client, type your query in the terminal.

Example queries:
- What weather tools do you have?
- Are there any alerts in California?
- What is the forecast for a location?

Type `quit` to exit the program.

## Important Notes

Make sure the following files and folders are not pushed to GitHub:
- `.env`
- `.venv`
- `venv`
- `__pycache__`

A typical `.gitignore` file should include:

.env
.venv/
venv/
__pycache__/
*.pyc