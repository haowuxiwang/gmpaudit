import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.notification import send_feishu_notification, notify_audit_complete, notify_high_risk_finding, notify_task_failed


@pytest.mark.asyncio
async def test_send_notification_no_webhook():
    with patch("app.services.notification.settings") as mock_settings:
        mock_settings.FEISHU_WEBHOOK_URL = None
        result = await send_feishu_notification("title", "content")
        assert result is False


@pytest.mark.asyncio
async def test_send_notification_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {"code": 0}

    with patch("app.services.notification.settings") as mock_settings:
        mock_settings.FEISHU_WEBHOOK_URL = "https://hooks.feishu.cn/test"
        mock_settings.FEISHU_WEBHOOK_SECRET = None
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await send_feishu_notification("测试标题", "测试内容", "high")
            assert result is True


@pytest.mark.asyncio
async def test_send_notification_api_error():
    mock_response = MagicMock()
    mock_response.json.return_value = {"code": 1, "msg": "error"}

    with patch("app.services.notification.settings") as mock_settings:
        mock_settings.FEISHU_WEBHOOK_URL = "https://hooks.feishu.cn/test"
        mock_settings.FEISHU_WEBHOOK_SECRET = None
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await send_feishu_notification("title", "content")
            assert result is False


@pytest.mark.asyncio
async def test_send_notification_network_error():
    with patch("app.services.notification.settings") as mock_settings:
        mock_settings.FEISHU_WEBHOOK_URL = "https://hooks.feishu.cn/test"
        mock_settings.FEISHU_WEBHOOK_SECRET = None
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=Exception("network error")):
            result = await send_feishu_notification("title", "content")
            assert result is False


@pytest.mark.asyncio
async def test_send_notification_statuscode_field():
    mock_response = MagicMock()
    mock_response.json.return_value = {"StatusCode": 0}

    with patch("app.services.notification.settings") as mock_settings:
        mock_settings.FEISHU_WEBHOOK_URL = "https://hooks.feishu.cn/test"
        mock_settings.FEISHU_WEBHOOK_SECRET = None
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await send_feishu_notification("title", "content")
            assert result is True


@pytest.mark.asyncio
async def test_send_notification_with_signature():
    mock_response = MagicMock()
    mock_response.json.return_value = {"code": 0}

    with patch("app.services.notification.settings") as mock_settings:
        mock_settings.FEISHU_WEBHOOK_URL = "https://hooks.feishu.cn/test"
        mock_settings.FEISHU_WEBHOOK_SECRET = "test_secret"
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            result = await send_feishu_notification("title", "content")
            assert result is True
            # Verify sign and timestamp were added to the payload
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert "timestamp" in payload
            assert "sign" in payload


@pytest.mark.asyncio
async def test_notify_audit_complete():
    with patch("app.services.notification.send_feishu_notification", new_callable=AsyncMock, return_value=True) as mock_send:
        await notify_audit_complete("测试任务", 10, 3, 5)
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert "测试任务" in call_args[0][0]
        assert call_args[0][2] == "high"  # high_count > 0


@pytest.mark.asyncio
async def test_notify_audit_complete_with_top_findings():
    with patch("app.services.notification.send_feishu_notification", new_callable=AsyncMock, return_value=True) as mock_send:
        top = [{"title": "关键偏差", "severity": "high"}, {"title": "文档缺失", "severity": "high"}]
        await notify_audit_complete("任务", 5, 2, 1, top)
        call_args = mock_send.call_args
        content = call_args[0][1]
        assert "关键偏差" in content
        assert "文档缺失" in content


@pytest.mark.asyncio
async def test_notify_audit_complete_medium_risk():
    with patch("app.services.notification.send_feishu_notification", new_callable=AsyncMock, return_value=True) as mock_send:
        await notify_audit_complete("任务", 5, 0, 3)
        call_args = mock_send.call_args
        assert call_args[0][2] == "medium"


@pytest.mark.asyncio
async def test_notify_audit_complete_low_risk():
    with patch("app.services.notification.send_feishu_notification", new_callable=AsyncMock, return_value=True) as mock_send:
        await notify_audit_complete("任务", 2, 0, 0)
        call_args = mock_send.call_args
        assert call_args[0][2] == "low"


@pytest.mark.asyncio
async def test_notify_high_risk_finding():
    with patch("app.services.notification.send_feishu_notification", new_callable=AsyncMock, return_value=True) as mock_send:
        await notify_high_risk_finding("任务", "严重偏差", "high", "发现重大偏差")
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert "严重偏差" in call_args[0][0]
        assert call_args[0][2] == "high"


@pytest.mark.asyncio
async def test_notify_task_failed():
    with patch("app.services.notification.send_feishu_notification", new_callable=AsyncMock, return_value=True) as mock_send:
        await notify_task_failed("测试任务", "连接超时")
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert "失败" in call_args[0][0]
        assert "连接超时" in call_args[0][1]
