from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from .db import Base

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

