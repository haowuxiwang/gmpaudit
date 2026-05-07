from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    feishu_open_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    email = Column(String(200), nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
