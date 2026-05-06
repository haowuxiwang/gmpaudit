from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class SeverityLevel(enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class FindingType(enum.Enum):
    LOGIC_FLAW = "logic_flaw"
    COMPLIANCE_RISK = "compliance_risk"
    INCONSISTENCY = "inconsistency"
    MISSING_INFO = "missing_info"
    BEST_PRACTICE = "best_practice"

class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("audit_tasks.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    finding_type = Column(Enum(FindingType), nullable=False)
    severity = Column(Enum(SeverityLevel), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)
    location = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
