import httpx
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_feishu_notification(title: str, content: str, risk_level: str = "info") -> bool:
    """Send a card message to Feishu group via webhook."""
    if not settings.FEISHU_WEBHOOK_URL:
        logger.warning("FEISHU_WEBHOOK_URL not configured, skipping notification")
        return False

    color_map = {
        "high": "red",
        "medium": "orange",
        "low": "green",
        "info": "blue"
    }

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": color_map.get(risk_level, "blue")
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content
                    }
                }
            ]
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.FEISHU_WEBHOOK_URL,
                json=card,
                timeout=10
            )
            result = response.json()
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                logger.info(f"Feishu notification sent: {title}")
                return True
            else:
                logger.error(f"Feishu notification failed: {result}")
                return False
    except Exception as e:
        logger.error(f"Feishu notification error: {e}")
        return False


async def notify_audit_complete(task_name: str, findings_count: int, high_count: int, medium_count: int):
    """Send audit completion notification."""
    risk_level = "high" if high_count > 0 else ("medium" if medium_count > 0 else "low")
    title = f"审计完成: {task_name}"
    content = (
        f"**任务:** {task_name}\n"
        f"**发现总数:** {findings_count}\n"
        f"**高风险:** {high_count} | **中风险:** {medium_count}\n"
    )
    await send_feishu_notification(title, content, risk_level)
