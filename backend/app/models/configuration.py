from sqlalchemy import Column, Integer, String, Text
from app.core.database import Base

class Configuration(Base):
    __tablename__ = "configurations"

    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, nullable=False)
    config_value = Column(Text, nullable=False)
    config_type = Column(String(50), nullable=False)
    description = Column(String(500), nullable=True)
