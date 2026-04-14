#AuthContext is the object during auth checks, it contains token informations
from fastmcp.server.auth import AuthContext
#Need the database sesson to make query
from database.db import SessionLocal
#Import the User model class
from database.model import User

#email is not a must thing to put
def get_or_create_user_from_github(github_login: str, email: str | None = None):
    #create a new database session
    db = SessionLocal()
    try:
        #filter(....) only rows whose GitHub login matches
        #.first() return first matching user, None if no match
        user = db.query(User).filter(User.github_login == github_login).first()
        #if the user exist
        if user:
            #if github bined email is not as the same sa the stored one, update it
            if email and user.email != email:
                user.email = email
                db.commit()
                db.refresh(user)
            return user
        else:
            #if the user does not exist at all
            user = User(
                github_login=github_login,
                email=email,
                role="user"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

    finally:
        db.close()

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
    #get the email if available
    email = ctx.token.claims.get("email")
    #link github authentication to local database
    user = get_or_create_user_from_github(github_login, email)
    #last check to make sure it is true
    return user is not None


def require_local_admin(ctx: AuthContext) -> bool:
    if ctx.token is None:
        return False

    github_login = ctx.token.claims.get("login")
    if not github_login:
        return False

    email = ctx.token.claims.get("email")
    user = get_or_create_user_from_github(github_login, email)

    return user is not None and user.role == "admin"