import httpx
import logging
import time
import hmac
import hashlib
from app.core.config import settings

logger = logging.getLogger(__name__)

_COLOR_MAP = {"high": "red", "medium": "orange", "low": "green", "info": "blue"}


def _build_sign(timestamp: str, secret: str) -> str:
    """Build HMAC-SHA256 signature for Feishu webhook."""
    string_to_sign = f"{timestamp}\n{secret}"
    return hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest().hex()


async def send_feishu_notification(title: str, content: str, risk_level: str = "info") -> bool:
    """Send a card message to Feishu group via webhook."""
    webhook_url = settings.FEISHU_WEBHOOK_URL
    if not webhook_url:
        logger.warning("FEISHU_WEBHOOK_URL not configured, skipping notification")
        return False

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": _COLOR_MAP.get(risk_level, "blue"),
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
            ],
        },
    }

    # Add signature if secret is configured
    secret = settings.FEISHU_WEBHOOK_SECRET
    if secret:
        timestamp = str(int(time.time()))
        sign = _build_sign(timestamp, secret)
        card["timestamp"] = timestamp
        card["sign"] = sign

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=card, timeout=10)
            result = response.json()
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                logger.info("Feishu notification sent: %s", title)
                return True
            logger.error("Feishu notification failed: %s", result)
            return False
    except Exception as e:
        logger.error("Feishu notification error: %s", e)
        return False


async def notify_audit_complete(
    task_name: str,
    findings_count: int,
    high_count: int,
    medium_count: int,
    top_findings: list[dict] | None = None,
):
    """Send audit completion notification with detailed card."""
    risk_level = "high" if high_count > 0 else ("medium" if medium_count > 0 else "low")
    title = f"审计完成: {task_name}"

    low_count = findings_count - high_count - medium_count

    # Risk distribution with columns
    risk_parts = []
    if high_count > 0:
        risk_parts.append(f"🔴 高风险: **{high_count}**")
    if medium_count > 0:
        risk_parts.append(f"🟡 中风险: **{medium_count}**")
    if low_count > 0:
        risk_parts.append(f"🟢 低风险: **{low_count}**")

    content = (
        f"**任务:** {task_name}\n"
        f"**发现总数:** {findings_count}\n"
        f"{' | '.join(risk_parts)}"
    )

    # Add top findings summary
    if top_findings:
        content += "\n\n---\n**关键发现:**\n"
        for i, f in enumerate(top_findings[:3], 1):
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(f.get("severity", ""), "⚪")
            content += f"{i}. {severity_icon} {f.get('title', '')}\n"

    await send_feishu_notification(title, content, risk_level)


async def notify_high_risk_finding(task_name: str, finding_title: str, severity: str, description: str):
    """Send immediate notification for high-risk findings."""
    title = f"⚠️ 高风险发现: {finding_title}"
    content = (
        f"**任务:** {task_name}\n"
        f"**严重程度:** {severity}\n"
        f"**描述:** {description[:200]}"
    )
    await send_feishu_notification(title, content, "high")


async def notify_task_failed(task_name: str, error_message: str):
    """Send notification when an audit task fails."""
    title = f"❌ 审计任务失败: {task_name}"
    content = (
        f"**任务:** {task_name}\n"
        f"**错误:** {error_message[:300]}"
    )
    await send_feishu_notification(title, content, "high")
