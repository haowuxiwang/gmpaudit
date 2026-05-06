from sqlalchemy import Column, Integer, String, DateTime, Text, Enum
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class DocumentStatus(enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    process_status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED)
    metadata = Column(Text, nullable=True)
    content_text = Column(Text, nullable=True)
    vector_id = Column(String(100), nullable=True)
