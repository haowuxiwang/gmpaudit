from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, JSON
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class TaskStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskType(enum.Enum):
    DEVIATION_ANALYSIS = "deviation_analysis"
    SOP_COMPLIANCE = "sop_compliance"
    CONSISTENCY_CHECK = "consistency_check"
    RISK_ASSESSMENT = "risk_assessment"

class AuditTask(Base):
    __tablename__ = "audit_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String(255), nullable=False)
    task_type = Column(Enum(TaskType), nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    config = Column(JSON, nullable=True)
    document_ids = Column(JSON, nullable=True)
    progress = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
