from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from database.db import engine, Base, get_db
from database import model
from database.model import User
from services.mcp_host import run_agent
app = FastAPI()
htmls = Jinja2Templates(directory="pages")
Base.metadata.create_all(bind=engine)

class ChatRequest(BaseModel):
    message: str
class RegisterRequest(BaseModel):
    username: str
    password: str


def hash_password(password: str) -> str:
    return hashed_password.hash(password)

@app.get("/")
async def home(req: Request):
    return htmls.TemplateResponse(req, "home.html")


@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        # temporary demo identity
        user_id = "user_123"

        reply = await run_agent(req.message, user_id)
        return {"reply": reply}
    except Exception as e:
        return {"error": str(e)}
    
@app.post("/register")
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == req.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        )

    db.add(new_user)
    #commit the changing to the database
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User created successfully",
        "username": new_user.username,
    }
