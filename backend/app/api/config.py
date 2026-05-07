from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.configuration import Configuration

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
    from app.services.llm_engine import get_llm_engine
    engine = get_llm_engine()
    providers = engine.get_available_providers()

    # Provider display names
    names = {
        "deepseek": "DeepSeek",
        "qwen": "通义千问",
        "glm": "智谱GLM",
        "openai": "OpenAI",
        "anthropic": "Anthropic/Claude",
        "siliconflow": "SiliconFlow",
        "openrouter": "OpenRouter",
        "mimo": "Mimo/MiniMax",
    }

    return [
        {
            "id": p["name"],
            "name": names.get(p["name"], p["name"]),
            "model": p["model"],
            "available": p["available"],
        }
        for p in providers
    ]
