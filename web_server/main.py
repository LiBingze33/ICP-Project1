from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from services.mcp_host import run_agent

app = FastAPI()
htmls = Jinja2Templates(directory="pages")


class ChatRequest(BaseModel):
    message: str


@app.get("/")
async def home(request: Request):
    # Starlette 1.0+ expects TemplateResponse(request, name, context)
    return htmls.TemplateResponse(request, "home.html")


@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        # temporary demo identity
        user_id = "user_123"

        reply = await run_agent(req.message, user_id)
        return {"reply": reply}
    except Exception as e:
        return {"error": str(e)}
