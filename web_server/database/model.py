from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from .db import Base

#database/model.py
#Defines the SQLAlchemy database models used by the web app.
#The User model stores GitHub identity, role, and private workspace information.
#SQLAlchemy maps
#Python class: User
#Database tableL users
class User(Base):
    #database table name
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    github_login = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=False, nullable=True)
    role = Column(String, nullable=False, default="user")
    workspace_path = Column(String, nullable=False)

