import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


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


class FindingStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("audit_tasks.id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    finding_type = Column(Enum(FindingType), nullable=False)
    severity = Column(Enum(SeverityLevel), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)
    location = Column(String(500), nullable=True)
    regulation_ref = Column(String(500), nullable=True)
    status = Column(
        Enum(FindingStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=FindingStatus.PENDING,
    )
    reviewer_comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
