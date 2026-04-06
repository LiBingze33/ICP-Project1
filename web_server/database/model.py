from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from .db import Base

#SQLAlchemy maps
#Python class: User
#Database tableL users
class User(Base):
    #database table name
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")
