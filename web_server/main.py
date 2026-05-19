import os
import json
import asyncio
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, StreamingResponse
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
#This add a middleware layer to the web app which is a built in feature
app.add_middleware(
    SessionMiddleware,
    #keys to protect the session cookie, so users cannot fake their login
    secret_key=os.getenv("SESSION_SECRET_KEY"),
    #Allow normal login, but do not send cookie everywhere
    same_site="lax",
    #make sure the session cookie is only sent over HTTPs
    https_only=True,
    max_age=60 * 60 * 2  # 2 hours)
)
oauth = OAuth()
#https://docs.authlib.org/en/v1.7.0/oauth2/client/web/flask.html
oauth.register(
    name="github",
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    #https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps
    #backend sends the returned code here to get the access token
    access_token_url="https://github.com/login/oauth/access_token",
    #the app sends the browser so the user can login
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
    #This is used after the user clicks "Yes" on the consent popup
    approved_risky_actions: list[str] = []

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
    #Authlib builds the Github Login URL
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
    # workspace_path = BASE_WORKSPACE_DIR / f"github_{github_login}"
    # workspace_path.mkdir(parents=True, exist_ok=True)
    workspace_folder = f"github_{github_login}"
    full_workspace_path = BASE_WORKSPACE_DIR / workspace_folder
    full_workspace_path.mkdir(parents=True, exist_ok=True)

    
    
    # Save or update user in local database
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.github_login == github_login).first()

        if not user:
            user = User(
                github_login=github_login,
                email=None,
                role="user",
                workspace_path=workspace_folder,

            )
            db.add(user)
            db.commit()
            db.refresh(user)


        else:
            # Always make sure the stored workspace path matches the current GitHub login.
            # Update worksapce if necessary
            if user.workspace_path != workspace_folder:
                user.workspace_path = workspace_folder
                db.commit()
                db.refresh(user)

            # Make sure the folder still exists
            (BASE_WORKSPACE_DIR / user.workspace_path).mkdir(parents=True, exist_ok=True)

                # Store logged-in user in session
        request.session["user"] = {
            "user_id": user.user_id,
            "login": user.github_login,
            "github_id": github_id,
            "avatar_url": avatar_url,
            # "role": user.role,
            # "workspace_path": user.workspace_path,

        }
    finally:
        db.close()
    #go back to home page
    return RedirectResponse(url="/")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")


# @app.post("/chat")
# async def chat(req: ChatRequest, request: Request):
#     try:
#         #check if the user is logged in and have a session
#         session_user = request.session.get("user")

#         if not session_user:
#             return {"error": "Please log in with GitHub before using the tools."}
#         #do not solely trust the session
#         # reply = await run_agent(req.message, user, req.backend)

#         #Check wether the session contains a valid identity value
#         github_login = session_user.get("login")
#         if not github_login:
#             #clear the session
#             request.session.clear()
#             return{"error":"Invalid session. Please login again"}

#         #Database user validation
#         #Check whether the logged-in GitHub user still exist
#         db = SessionLocal()
#         try:
#             db_user = db.query(User).filter(User.github_login == github_login).first()

#             if not db_user:
#                 request.session.clear()
#                 return {"error": "User no longer exists. Please log in again."}


#             #Create a user text from the database
#             #Avoids simply trusting role/worksapce from the session
#             trusted_user = {
#             "user_id": db_user.user_id,
#             "login": db_user.github_login,
#             "role": db_user.role,
#             #the file tool still need full path internally
#             "workspace_path": str((BASE_WORKSPACE_DIR / db_user.workspace_path).resolve()),
#             }
#             reply = await run_agent(req.message, trusted_user, req.backend)

#             return {
#                 "reply": reply,
#                 "backend_used": req.backend,
#             }
#         finally:
#             db.close()
#     except Exception as e:
#         return {"error": str(e)}
    
@app.post("/chat-stream")
async def chat_stream(req: ChatRequest, request: Request):

    async def generate_logs():
        try:
            #send the message to the frontend, but do not finish the whole response
            #json.dumps convert python dictonary into Json Text
            #data is for SSE streaming
            #https://fastapi.tiangolo.com/advanced/stream-data/
            
            yield "data: " + json.dumps({
                "type": "log",
                "content": "Request received from frontend."
            }) + "\n\n"
            await asyncio.sleep(0.3)

            yield "data: " + json.dumps({
                "type": "log",
                "content": f"Selected backend: {req.backend}"
            }) + "\n\n"
            await asyncio.sleep(0.3)

            # Check login session
            session_user = request.session.get("user")

            if not session_user:
                yield "data: " + json.dumps({
                    "type": "error",
                    "content": "Please log in with GitHub before using the tools."
                }) + "\n\n"
                return

            yield "data: " + json.dumps({
                "type": "log",
                "content": "Session check passed. User is logged in."
            }) + "\n\n"
            await asyncio.sleep(0.3)

            # Check whether the session contains GitHub login
            github_login = session_user.get("login")

            if not github_login:
                request.session.clear()
                yield "data: " + json.dumps({
                    "type": "error",
                    "content": "Invalid session. Please login again."
                }) + "\n\n"
                return

            yield "data: " + json.dumps({
                "type": "log",
                "content": f"GitHub login found: {github_login}"
            }) + "\n\n"
            await asyncio.sleep(0.3)

            # Database validation
            db = SessionLocal()

            try:
                yield "data: " + json.dumps({
                    "type": "log",
                    "content": "Checking user in local database."
                }) + "\n\n"
                await asyncio.sleep(0.3)

                db_user = db.query(User).filter(User.github_login == github_login).first()

                if not db_user:
                    request.session.clear()
                    yield "data: " + json.dumps({
                        "type": "error",
                        "content": "User no longer exists. Please log in again."
                    }) + "\n\n"
                    return
            #Create a user text from the database
            #Avoids simply trusting role/worksapce from the session
                trusted_user = {
                    "user_id": db_user.user_id,
                    "login": db_user.github_login,
                    "role": db_user.role,
                    "workspace_path": str((BASE_WORKSPACE_DIR / db_user.workspace_path).resolve()),

                }

                yield "data: " + json.dumps({
                    "type": "log",
                    "content": f"Database validation passed. Role: {db_user.role}"
                }) + "\n\n"
                await asyncio.sleep(0.3)

                yield "data: " + json.dumps({
                    "type": "log",
                    "content": f"Workspace path loaded: {db_user.workspace_path}"
                }) + "\n\n"
                await asyncio.sleep(0.3)

                yield "data: " + json.dumps({
                    "type": "log",
                    "content": "Starting agent processing."
                }) + "\n\n"
                await asyncio.sleep(0.3)

                yield "data: " + json.dumps({
                    "type": "log",
                    "content": "Sending message to selected model backend."
                }) + "\n\n"
                await asyncio.sleep(0.3)

                log_queue = asyncio.Queue()

                async def emit(message):
                    # Normal text log
                    if isinstance(message, str):
                        await log_queue.put({
                            "type": "log",
                            "content": message
                        })
                        return

                    # Special event, for example:
                    # {"type": "consent_required", ...}
                    #consent needs to send a special frontend event like
                    #{
                    #   "type": "consent_required",
                    #   "content": "This action will delete a file."
                    #}
                    if isinstance(message, dict):
                        await log_queue.put(message)
                        return

                agent_task = asyncio.create_task(
                    run_agent(
                        req.message, 
                        trusted_user, 
                        req.backend, 
                        emit=emit,
                        approved_risky_actions = req.approved_risky_actions,
                          )
                )

                while not agent_task.done() or not log_queue.empty():
                    while not log_queue.empty():
                        log_item = await log_queue.get()
                        yield "data: " + json.dumps(log_item) + "\n\n"

                    await asyncio.sleep(0.1)

                reply = await agent_task
                yield "data: " + json.dumps({
                    "type": "log",
                    "content": "Agent finished processing."
                }) + "\n\n"
                await asyncio.sleep(0.3)

                yield "data: " + json.dumps({
                    "type": "log",
                    "content": "Preparing final response for frontend."
                }) + "\n\n"
                await asyncio.sleep(0.3)

                yield "data: " + json.dumps({
                    "type": "final",
                    "content": reply
                }) + "\n\n"

            finally:
                db.close()
        #Chat Strem Error
        except Exception as e:
            yield "data: " + json.dumps({
                "type": "error",
                "content": str(e)
            }) + "\n\n"

    return StreamingResponse(generate_logs(), media_type="text/event-stream")