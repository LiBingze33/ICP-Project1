import os
import jwt
from dotenv import load_dotenv
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_request
from fastmcp.server.middleware import Middleware, MiddlewareContext
#https://gofastmcp.com/servers/middleware
load_dotenv()

INTERNAL_JWT_SECRET = os.getenv("INTERNAL_JWT_SECRET")

if not INTERNAL_JWT_SECRET:
    raise RuntimeError("INTERNAL_JWT_SECRET is missing from .env")


def verify_internal_jwt(auth_header: str) -> dict:
    # Verify the internal JWT sent by mcp_host.py.
    # This proves the request came from the trusted backend service.
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ToolError("Missing internal JWT")

    token = auth_header.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(
            token,
            INTERNAL_JWT_SECRET,
            algorithms=["HS256"],
            audience="mcp-server",
            issuer="fastapi-web",
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise ToolError("Internal JWT expired")

    except jwt.InvalidTokenError:
        raise ToolError("Invalid internal JWT")


class InternalJWTMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        
        print(f"JWT middleware checking request: {context.method}")

        # Check the JWT before allowing any MCP request to continue.
        request = get_http_request()
        auth_header = request.headers.get("Authorization")

        verify_internal_jwt(auth_header)
        #call_next is the funciton which ccontinues to the next middleware or the actual MCP operation
        print(f"JWT check passed for request: {context.method}")

        return await call_next(context)