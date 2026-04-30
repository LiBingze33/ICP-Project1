import os

from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from typing import Literal
from database.model import User
from database.db import engine, Base, SessionLocal
from services.mcp_host import run_agent
from pathlib import Path
#FastAPI web app with GitHub OAuth Login
load_dotenv()
BASE_WORKSPACE_DIR = Path("user_workspaces").resolve()
app = FastAPI()
#add session support to the FastAPI app, so the app can remember who logged in
#This add a middleware layer to the web app
app.add_middleware(
    SessionMiddleware,
    #keys to protect the session cookie, so users cannot fake their login
    secret_key=os.getenv("SESSION_SECRET_KEY"),
    #Allow normal login, but do not send cookie everywhere
    same_site="lax",
    #make sure the session cookie is only sent over HTTPs
    # https_only=True,
)

oauth = OAuth()
#https://docs.authlib.org/en/v1.7.0/oauth2/client/web/flask.html
oauth.register(
    name="github",
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    #https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps
    #the app sends the browser so the user can login
    access_token_url="https://github.com/login/oauth/access_token",
    #backend sends the retuened code to get the access token
    authorize_url="https://github.com/login/oauth/authorize",
    #for the convenience to to simplify the base url
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "read:user user:email"},
)

htmls = Jinja2Templates(directory="pages")

# SQLAlchemy will create the users table here
Base.metadata.create_all(bind=engine)


class ChatRequest(BaseModel):
    message: str
    backend: Literal["openrouter", "ollama"] = "openrouter"

#Homepage
@app.get("/")
async def home(req: Request):
    #this will retrive the whole session
    user = req.session.get("user")

    username = None
    if user:
        username = user.get("login")

    return htmls.TemplateResponse(
        req,
        "home.html",
        {"user": username},
    )


@app.get("/login")
async def login(request: Request):
    redirect_uri = "http://127.0.0.1:8000/auth/callback"
    return await oauth.github.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    # Get access token from GitHub
    token = await oauth.github.authorize_access_token(request)

    # Use token to get GitHub user profile
    res = await oauth.github.get("user", token=token)
    github_user = res.json()
    github_login = github_user.get("login")
    github_id = github_user.get("id")
    avatar_url = github_user.get("avatar_url")

    if not github_login:
        return {"error": "GitHub login was not found."}

    
    
    # Create a stable workspace folder for this GitHub user
    workspace_path = BASE_WORKSPACE_DIR / f"github_{github_login}"
    workspace_path.mkdir(parents=True, exist_ok=True)

    
    
    
    # Save or update user in local database
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.github_login == github_login).first()

        if not user:
            user = User(
                github_login=github_login,
                email=None,
                role="user",
                workspace_path=str(workspace_path),

            )
            db.add(user)
            db.commit()
            db.refresh(user)


        else:
            # Always make sure the stored workspace path matches the current GitHub login.
            # Update worksapce if necessary
            if user.workspace_path != str(workspace_path):
                user.workspace_path = str(workspace_path)
                db.commit()
                db.refresh(user)

            # Make sure the folder still exists
            Path(user.workspace_path).mkdir(parents=True, exist_ok=True)

                # Store logged-in user in session
        request.session["user"] = {
            "user_id": user.user_id,
            "login": user.github_login,
            "github_id": github_id,
            "avatar_url": avatar_url,
            "role": user.role,
            "workspace_path": user.workspace_path,

        }
    finally:
        db.close()

    return RedirectResponse(url="/")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")


@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    try:
        #check if the user is logged in and have a session
        user = request.session.get("user")

        if not user:
            return {"error": "Please log in with GitHub before using the tools."}

        reply = await run_agent(req.message, user, req.backend)
        return {
            "reply": reply,
            "backend_used": req.backend,
}

    except Exception as e:
        return {"error": str(e)}