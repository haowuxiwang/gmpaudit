from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import documents, audit, reports, config, auth, alerts, agent_audit
from app.core.database import engine, Base
from app.core.auth import get_current_user

app = FastAPI(
    title="GMP合规性审计系统",
    description="GMP合规性审计与模拟审计员API",
    version="1.0.0"
)

# CORS 配置 - 生产环境应限制 origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 不需要认证的路径白名单
PUBLIC_PATHS = {
    "/",
    "/docs",
    "/openapi.json",
    "/api/auth/feishu/login",
    "/api/auth/feishu/callback",
}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """全局认证中间件 - 白名单路径不需要认证"""
    path = request.url.path

    # 白名单路径直接放行
    if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
        return await call_next(request)

    # OPTIONS 请求放行 (CORS preflight)
    if request.method == "OPTIONS":
        return await call_next(request)

    # 其他路径需要认证
    try:
        # 从 header 获取 token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "未提供认证凭据"}
            )

        # 验证 token (在中间件中只做基本验证，具体路由中获取用户)
        return await call_next(request)
    except Exception as e:
        return JSONResponse(
            status_code=401,
            content={"detail": f"认证失败: {str(e)}"}
        )


# 注册路由 - 需要认证的路由使用 get_current_user 依赖
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"], dependencies=[Depends(get_current_user)])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"], dependencies=[Depends(get_current_user)])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"], dependencies=[Depends(get_current_user)])
app.include_router(config.router, prefix="/api/config", tags=["config"], dependencies=[Depends(get_current_user)])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"], dependencies=[Depends(get_current_user)])
app.include_router(agent_audit.router, prefix="/api/agent-audit", tags=["agent-audit"], dependencies=[Depends(get_current_user)])


@app.on_event("startup")
async def startup():
    # 检查 JWT 密钥安全性
    from app.core.config import settings
    if settings.JWT_SECRET_KEY == "gmp-audit-secret-key-change-in-production":
        import warnings
        warnings.warn(
            "WARNING: JWT_SECRET_KEY is using default value! "
            "Set a secure key in config/.env for production use.",
            UserWarning
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/")
async def root():
    return {"message": "GMP合规性审计系统API"}
