from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
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
    files = relationship("OwnedFile", back_populates="owner", cascade="all, delete-orphan")


class OwnedFile(Base):
    __tablename__ = "owned_files"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "logical_name", name="uq_owned_files_owner_name"),
    )

    file_id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    logical_name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    owner = relationship("User", back_populates="files")
