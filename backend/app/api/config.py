from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.configuration import Configuration
from app.core.config import settings

router = APIRouter()

@router.get("/")
async def get_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Configuration))
    configs = result.scalars().all()
    return {c.config_key: {"value": c.config_value, "type": c.config_type, "description": c.description} for c in configs}

@router.get("/{key}")
async def get_config_by_key(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Configuration).where(Configuration.config_key == key))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return {"key": config.config_key, "value": config.config_value, "type": config.config_type, "description": config.description}

@router.put("/{key}")
async def update_config(key: str, value: str, description: str = None, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Configuration).where(Configuration.config_key == key))
    config = result.scalar_one_or_none()

    if config:
        config.config_value = value
        if description:
            config.description = description
    else:
        config = Configuration(config_key=key, config_value=value, config_type="string", description=description)
        db.add(config)

    await db.commit()
    return {"status": "success"}

@router.get("/llm/models")
async def get_available_models():
    models = []
    if settings.DEEPSEEK_API_KEY:
        models.append({"id": "deepseek", "name": "DeepSeek", "description": "DeepSeek Chat模型"})
    if settings.QWEN_API_KEY:
        models.append({"id": "qwen", "name": "通义千问", "description": "阿里云通义千问模型"})
    if settings.GLM_API_KEY:
        models.append({"id": "glm", "name": "智谱GLM", "description": "智谱AI GLM模型"})
    return models
