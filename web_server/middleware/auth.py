#AuthContext is the object during auth checks, it contains token informations
from fastmcp.server.auth import AuthContext
#Need the database sesson to make query
from database.db import SessionLocal
#Import the User model class
from database.model import User


#ctx -> expect auth context object
def require_local_user(ctx: AuthContext) -> bool:
    #if no token, reject immediately
    if ctx.token is None:
        return False
    #try to get the login claim from the token, in Github, it will get the name
    github_login = ctx.token.claims.get("login")
    #if the token does not have a Github login, then reject
    if not github_login:
        return False
    db = SessionLocal()    
    try:
        user = db.query(User).filter(User.github_login == github_login).first()
        #return true if the user exists and return false if the use does not exist
        return user is not None
    #last check to make sure it is true
    finally:
        db.close()


def require_local_admin(ctx: AuthContext) -> bool:
    if ctx.token is None:
        return False

    github_login = ctx.token.claims.get("login")
    if not github_login:
        return False

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.github_login == github_login).first()
        return user is not None and user.role == "admin"
    finally:
        db.close()