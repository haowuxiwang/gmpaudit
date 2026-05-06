from .documents import router as documents_router
from .audit import router as audit_router
from .reports import router as reports_router
from .config import router as config_router

__all__ = [
    "documents_router",
    "audit_router",
    "reports_router",
    "config_router"
]
