from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import documents, audit, reports, config
from app.core.database import engine, Base

app = FastAPI(
    title="GMP合规性审计系统",
    description="GMP合规性审计与模拟审计员API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(config.router, prefix="/api/config", tags=["config"])

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def root():
    return {"message": "GMP合规性审计系统API"}
