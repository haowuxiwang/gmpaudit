from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, JSON, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class ReportType(enum.Enum):
    FULL_REPORT = "full_report"
    SUMMARY = "summary"
    RISK_ALERT = "risk_alert"

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("audit_tasks.id"), nullable=False)
    report_type = Column(Enum(ReportType), nullable=False)
    title = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    report_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
