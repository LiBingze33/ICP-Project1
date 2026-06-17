import os
import json
import asyncio
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from middleware.pre_check import PreCheckMiddleware
from middleware.response_check import check_response_details
from typing import Literal
from database.model import User
from database.db import engine, Base, SessionLocal
from services.mcp_host import run_agent
from services.upload_processing import (
    build_uploaded_file_prompt,
    build_uploaded_image_prompt,
    decode_uploaded_text_file,
    extract_uploaded_pdf_text,
)
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


# class ChatRequest(BaseModel):
#     message: str
#     backend: Literal["openrouter", "ollama"] = "openrouter"
#     #This is used after the user clicks "Yes" on the consent popup
#     approved_risky_actions: list[str] = []

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

#this /logout only logged the user out of the FastAPI app, not out of Github
# @app.get("/login")
# async def login(request: Request):
#     redirect_uri = "http://127.0.0.1:8000/auth/callback"
#     #Authlib builds the Github Login URL
#     return await oauth.github.authorize_redirect(request, redirect_uri)
@app.get("/login")
async def login(request: Request):
    #Build the URL for the route handled by the function called auth_callback
    redirect_uri = request.url_for("auth_callback")

    return await oauth.github.authorize_redirect(
        request,
        redirect_uri,
        #to force Github to ask again
        prompt="select_account"
    )


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
# @app.get("/logout")
# async def logout(request: Request):
#     request.session.clear()
#     return RedirectResponse(url="/")
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()

    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session")

    return response

    
@app.post("/chat-stream")
# instead of using JSON body, we use FormData because it is easier to send files and multiple fields from the frontend
async def chat_stream(
    request: Request,
    message: str = Form(...),
    backend: Literal["openrouter", "ollama"] = Form("openrouter"),
    approved_risky_actions: str = Form("[]"),
    uploaded_file: UploadFile | None = File(None),
):
    # approved_risky_actions is sent from the frontend as a JSON string,
    # so we convert it back into a Python list.
    try:
        approved_actions_list = json.loads(approved_risky_actions)
        if not isinstance(approved_actions_list, list):
            approved_actions_list = []
    except json.JSONDecodeError:
        approved_actions_list = []

    # These variables store the uploaded file before the streaming response starts.
    uploaded_file_bytes = None
    uploaded_file_mime_type = None
    uploaded_file_name = None

    if uploaded_file is not None:
        uploaded_file_bytes = await uploaded_file.read()
        uploaded_file_mime_type = uploaded_file.content_type
        uploaded_file_name = uploaded_file.filename

    async def generate_logs():
        try:
            # send the message to the frontend, but do not finish the whole response
            # json.dumps convert python dictionary into JSON text
            # data is for SSE streaming
            # https://fastapi.tiangolo.com/advanced/stream-data/

            yield "data: " + json.dumps({
                "type": "log",
                "content": "Request received from frontend."
            }) + "\n\n"
            await asyncio.sleep(0.3)

            yield "data: " + json.dumps({
                "type": "log",
                "content": f"Selected backend: {backend}"
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

                # Create a trusted user context from the database
                # Avoids simply trusting role/workspace from the session
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

                uploaded_file_saved_name = None

                # These variables decide whether the uploaded file should also be passed to the model.
                image_bytes_for_model = None
                image_mime_type_for_model = None
                uploaded_content_for_model = ""
                uploaded_content_type_for_model = ""

                # If the user uploaded a file, save it into the user's private workspace.
                if uploaded_file_bytes is not None and uploaded_file_name:
                    # Path(...).name removes any folder path from the uploaded filename.
                    # This helps prevent path traversal through uploaded filenames.
                    safe_name = Path(uploaded_file_name).name

                    allowed_suffixes = {
                        ".txt",
                        ".md",
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".pdf",
                    }

                    suffix = Path(safe_name).suffix.lower()

                    # Only allow selected file types for the demo.
                    if suffix not in allowed_suffixes:
                        yield "data: " + json.dumps({
                            "type": "error",
                            "content": "File type is not allowed."
                        }) + "\n\n"
                        return
                    # Check uploaded filename before saving
                    PreCheckMiddleware.reject_unsafe_text(safe_name)

                    # If the uploaded file is text-like or PDF, extract text so
                    # the model can summarise it after security checks.
                    uploaded_content_for_model = ""

                    if suffix in {".txt", ".md"}:
                        try:
                            uploaded_content_for_model = decode_uploaded_text_file(
                                uploaded_file_bytes,
                                safe_name,
                            )
                        except ValueError as exc:
                            yield "data: " + json.dumps({
                                "type": "error",
                                "content": str(exc)
                            }) + "\n\n"
                            return

                        uploaded_content_type_for_model = "text"

                    if suffix == ".pdf":
                        try:
                            uploaded_content_for_model = extract_uploaded_pdf_text(
                                uploaded_file_bytes,
                                safe_name,
                            )
                        except (RuntimeError, ValueError) as exc:
                            yield "data: " + json.dumps({
                                "type": "error",
                                "content": str(exc)
                            }) + "\n\n"
                            return

                        uploaded_content_type_for_model = "pdf"

                    if uploaded_content_for_model:
                        # Keep existing pre-call input checks, then run the
                        # post-call response checker on extracted content before
                        # it is allowed into the model context.
                        PreCheckMiddleware.reject_unsafe_text(uploaded_content_for_model)

                        content_check = check_response_details(
                            uploaded_content_for_model,
                            source=f"Uploaded file content from {safe_name}",
                        )

                        if content_check.blocked:
                            yield "data: " + json.dumps({
                                "type": "log",
                                "content": (
                                    "Uploaded file content blocked by "
                                    "post-call security check."
                                )
                            }) + "\n\n"
                            yield "data: " + json.dumps({
                                "type": "error",
                                "content": content_check.text
                            }) + "\n\n"
                            return

                        uploaded_content_for_model = content_check.text

                    workspace_dir = Path(trusted_user["workspace_path"]).resolve()
                    save_path = (workspace_dir / safe_name).resolve()

                    # Make sure the final save path is still inside the user's workspace.
                    if workspace_dir not in save_path.parents and save_path != workspace_dir:
                        yield "data: " + json.dumps({
                            "type": "error",
                            "content": "Invalid upload path."
                        }) + "\n\n"
                        return

                    # Save the uploaded file into the user workspace.
                    
                    save_path.write_bytes(uploaded_file_bytes)
                    uploaded_file_saved_name = safe_name

                    yield "data: " + json.dumps({
                        "type": "log",
                        "content": f"Uploaded file saved to workspace: {safe_name}"
                    }) + "\n\n"
                    await asyncio.sleep(0.3)

                    # If the uploaded file is an image, pass it to the vision-capable model.
                    if uploaded_file_mime_type and uploaded_file_mime_type.startswith("image/"):
                        image_bytes_for_model = uploaded_file_bytes
                        image_mime_type_for_model = uploaded_file_mime_type
                        uploaded_content_type_for_model = "image"

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
                    # consent needs to send a special frontend event like
                    # {
                    #   "type": "consent_required",
                    #   "content": "This action will delete a file."
                    # }
                    if isinstance(message, dict):
                        await log_queue.put(message)
                        return

                # The model receives the normal user message by default.
                message_for_model = message

                if uploaded_content_for_model:
                    message_for_model = build_uploaded_file_prompt(
                        message=message,
                        filename=uploaded_file_saved_name,
                        content_type=uploaded_content_type_for_model,
                        extracted_text=uploaded_content_for_model,
                    )

                if image_bytes_for_model is not None and uploaded_file_saved_name:
                    message_for_model = build_uploaded_image_prompt(
                        message=message,
                        filename=uploaded_file_saved_name,
                        content_type=image_mime_type_for_model or "image",
                    )

                agent_task = asyncio.create_task(
                    run_agent(
                        message_for_model,
                        trusted_user,
                        backend,
                        emit=emit,
                        approved_risky_actions=approved_actions_list,
                        image_bytes=image_bytes_for_model,
                        image_mime_type=image_mime_type_for_model,
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

        # Chat Stream Error
        except Exception as e:
            yield "data: " + json.dumps({
                "type": "error",
                "content": str(e)
            }) + "\n\n"

    return StreamingResponse(generate_logs(), media_type="text/event-stream")
