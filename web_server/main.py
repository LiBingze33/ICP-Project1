import os

from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from database import model
from database.db import engine, Base, SessionLocal
from services.mcp_host import run_agent
#FastAPI web app with GitHub OAuth Login
load_dotenv()

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
    https_only=True,
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

#Homepage
@app.get("/")
async def home(req: Request):
    user = req.session.get("user")
    return htmls.TemplateResponse(
        req,
        "home.html",
        {"user": user},
    )


@app.get("/login")
async def login(request: Request):
    redirect_uri = "https://9163.syslab.au/auth/callback"
    return await oauth.github.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    #This is just to get the access toekn, not enough to get an idea of who just logged in
    token = await oauth.github.authorize_access_token(request)
    #use the token to call GitHub's API and get the user profile
    res = await oauth.github.get("user", token=token)
    github_user = res.json()

    request.session["user"] = {
        "login": github_user.get("login"),
        "id": github_user.get("id"),
        "avatar_url": github_user.get("avatar_url"),
    }

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

        reply = await run_agent(req.message, user)
        return {"reply": reply}

    except Exception as e:
        return {"error": str(e)}