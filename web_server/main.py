from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from database import model
from database.db import engine, Base
from services.mcp_host import run_agent
app = FastAPI()
htmls = Jinja2Templates(directory="pages")
#the SQLAlchemy will create the users table here
Base.metadata.create_all(bind=engine)

class ChatRequest(BaseModel):
    message: str


@app.get("/")
async def home(req: Request):
    return htmls.TemplateResponse(req, "home.html")


@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        # temporary demo identity
        # user_id = "user_123"

        reply = await run_agent(req.message)
        return {"reply": reply}
    except Exception as e:
        return {"error": str(e)}
    
