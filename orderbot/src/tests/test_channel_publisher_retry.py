"""
Test channel publisher retry mechanisms and failure scenarios.

Tests the 3-attempt exponential backoff retry logic in publish_order_to_channel
and edit_order_message functions, covering success after retry and final failure.
"""
import os
import pytest
from unittest import mock
from aiogram.types import Message as TgMessage

from ..core.models import Order, OrderStatus
from ..services import channel_publisher


class MockBot:
    """Mock Bot that can simulate failures and success on specific attempts."""
    
    def __init__(self, fail_attempts=None, success_message_id=12345):
        self.fail_attempts = fail_attempts or []  # list of attempt numbers that should fail
        self.success_message_id = success_message_id
        self.call_count = 0
        self.calls = []  # track all calls for verification
    
    async def send_message(self, chat_id, text, reply_markup=None, disable_web_page_preview=True, parse_mode=None):
        self.call_count += 1
        call_info = {
            'method': 'send_message',
            'attempt': self.call_count,
            'chat_id': chat_id,
            'text_length': len(text),
            'has_reply_markup': reply_markup is not None
        }
        self.calls.append(call_info)
        
        if self.call_count in self.fail_attempts:
            raise Exception(f"Simulated network error on attempt {self.call_count}")
        
        # Return mock message
        return type('Message', (), {'message_id': self.success_message_id})()
    
    async def edit_message_text(self, chat_id, message_id, text, reply_markup=None, disable_web_page_preview=True, parse_mode=None):
        self.call_count += 1
        call_info = {
            'method': 'edit_message_text', 
            'attempt': self.call_count,
            'chat_id': chat_id,
            'message_id': message_id,
            'text_length': len(text),
            'has_reply_markup': reply_markup is not None
        }
        self.calls.append(call_info)
        
        if self.call_count in self.fail_attempts:
            raise Exception(f"Simulated edit error on attempt {self.call_count}")


@pytest.mark.asyncio
async def test_publish_success_first_attempt(monkeypatch):
    """Test successful publish on first attempt."""
    monkeypatch.setenv("BOT_TOKEN", "fake_token")
    monkeypatch.setenv("CHANNEL_ID", "-1001234567890")
    
    # Reset module-level globals
    from ..services import channel_publisher as cp
    import importlib
    importlib.reload(cp)
    
    mock_bot = MockBot(fail_attempts=[])
    
    with mock.patch.object(cp, '_ensure_bot', return_value=mock_bot):
        order = Order(
            id=1, 
            title="Test Order",
            content="Test content", 
            amount=99.9,
            status=OrderStatus.NEW,
            created_by=123,
            created_by_username="testuser"
        )
        
        message_id = await cp.publish_order_to_channel(order)
        
        assert message_id == 12345
        assert mock_bot.call_count == 1
        assert mock_bot.calls[0]['method'] == 'send_message'
        assert mock_bot.calls[0]['chat_id'] == -1001234567890


@pytest.mark.asyncio  
async def test_publish_success_after_retry(monkeypatch):
    """Test successful publish on second attempt after first failure."""
    monkeypatch.setenv("BOT_TOKEN", "fake_token")
    monkeypatch.setenv("CHANNEL_ID", "-1001234567890")
    
    import orderbot.src.services.channel_publisher as cp
    import importlib
    importlib.reload(cp)
    
    # speed up retries
    async def fast_sleep(_):
        return None
    monkeypatch.setattr(cp.asyncio, "sleep", fast_sleep)

    # Fail on first attempt, succeed on second
    mock_bot = MockBot(fail_attempts=[1])
    
    with mock.patch.object(cp, '_ensure_bot', return_value=mock_bot):
        order = Order(
            id=2,
            title="Retry Test", 
            content="Retry content",
            amount=None,
            status=OrderStatus.NEW,
            created_by=456,
            created_by_username="retryuser"
        )
        
        message_id = await cp.publish_order_to_channel(order)
        
        assert message_id == 12345
        assert mock_bot.call_count == 2  # failed once, succeeded on retry
        assert all(call['method'] == 'send_message' for call in mock_bot.calls)


@pytest.mark.asyncio
async def test_publish_final_failure_after_3_attempts(monkeypatch):
    """Test final failure after all 3 attempts fail."""
    monkeypatch.setenv("BOT_TOKEN", "fake_token")  
    monkeypatch.setenv("CHANNEL_ID", "-1001234567890")
    
    import orderbot.src.services.channel_publisher as cp
    import importlib
    importlib.reload(cp)
    
    # speed up retries
    async def fast_sleep(_):
        return None
    monkeypatch.setattr(cp.asyncio, "sleep", fast_sleep)

    # Fail all 3 attempts
    mock_bot = MockBot(fail_attempts=[1, 2, 3])
    
    with mock.patch.object(cp, '_ensure_bot', return_value=mock_bot):
        order = Order(
            id=3,
            title="Failure Test",
            content="This will fail",
            amount=50.0,
            status=OrderStatus.NEW, 
            created_by=789,
            created_by_username="failuser"
        )
        
        message_id = await cp.publish_order_to_channel(order)
        
        assert message_id is None  # final failure returns None
        assert mock_bot.call_count == 3  # tried 3 times
        assert all(call['method'] == 'send_message' for call in mock_bot.calls)


@pytest.mark.asyncio
async def test_edit_success_first_attempt(monkeypatch):
    """Test successful edit on first attempt."""
    monkeypatch.setenv("BOT_TOKEN", "fake_token")
    monkeypatch.setenv("CHANNEL_ID", "-1001234567890")
    
    import orderbot.src.services.channel_publisher as cp
    import importlib
    importlib.reload(cp)
    
    mock_bot = MockBot(fail_attempts=[])
    
    with mock.patch.object(cp, '_ensure_bot', return_value=mock_bot):
        order = Order(
            id=4,
            title="Edit Test",
            content="Edit content",
            amount=25.5,
            status=OrderStatus.CLAIMED,
            created_by=111,
            created_by_username="creator",
            claimed_by=222,
            claimed_by_username="claimer",
            channel_message_id=9876
        )
        
        await cp.edit_order_message(order)
        
        assert mock_bot.call_count == 1
        call = mock_bot.calls[0]
        assert call['method'] == 'edit_message_text'
        assert call['message_id'] == 9876
        assert call['chat_id'] == -1001234567890


@pytest.mark.asyncio
async def test_edit_success_after_retry(monkeypatch):
    """Test successful edit on third attempt after two failures."""
    monkeypatch.setenv("BOT_TOKEN", "fake_token")
    monkeypatch.setenv("CHANNEL_ID", "-1001234567890")
    
    import orderbot.src.services.channel_publisher as cp
    import importlib
    importlib.reload(cp)
    
    # speed up retries
    async def fast_sleep(_):
        return None
    monkeypatch.setattr(cp.asyncio, "sleep", fast_sleep)

    # Fail first two attempts, succeed on third
    mock_bot = MockBot(fail_attempts=[1, 2])
    
    with mock.patch.object(cp, '_ensure_bot', return_value=mock_bot):
        order = Order(
            id=5,
            title="Edit Retry Test",
            content="Edit retry content", 
            amount=None,
            status=OrderStatus.DONE,
            created_by=333,
            created_by_username="creator2",
            claimed_by=444, 
            claimed_by_username="finisher",
            channel_message_id=5555
        )
        
        await cp.edit_order_message(order)
        
        assert mock_bot.call_count == 3  # failed twice, succeeded on third
        assert all(call['method'] == 'edit_message_text' for call in mock_bot.calls)
        assert all(call['message_id'] == 5555 for call in mock_bot.calls)


@pytest.mark.asyncio
async def test_edit_final_failure_after_3_attempts(monkeypatch):
    """Test edit final failure after all 3 attempts fail."""
    monkeypatch.setenv("BOT_TOKEN", "fake_token")
    monkeypatch.setenv("CHANNEL_ID", "-1001234567890")
    
    import orderbot.src.services.channel_publisher as cp
    import importlib  
    importlib.reload(cp)
    
    # speed up retries
    async def fast_sleep(_):
        return None
    monkeypatch.setattr(cp.asyncio, "sleep", fast_sleep)

    # All 3 attempts fail
    mock_bot = MockBot(fail_attempts=[1, 2, 3])
    
    with mock.patch.object(cp, '_ensure_bot', return_value=mock_bot):
        order = Order(
            id=6,
            title="Edit Failure Test",
            content="This edit will fail completely",
            amount=100.0,
            status=OrderStatus.IN_PROGRESS,
            created_by=555,
            created_by_username="creator3",
            claimed_by=666,
            claimed_by_username="worker", 
            channel_message_id=7777
        )
        
        # Should not raise, but log error internally
        await cp.edit_order_message(order)
        
        assert mock_bot.call_count == 3  # attempted 3 times
        assert all(call['method'] == 'edit_message_text' for call in mock_bot.calls)


@pytest.mark.asyncio
async def test_publish_skips_when_message_id_exists():
    """Test publish is idempotent when order already has channel_message_id."""
    order = Order(
        id=7,
        title="Already Published",
        content="Already has message ID",
        amount=None,
        status=OrderStatus.NEW,
        created_by=777,
        created_by_username="existing",
        channel_message_id=8888  # Already set
    )
    
    # Should return existing message_id without any network calls
    message_id = await channel_publisher.publish_order_to_channel(order)
    assert message_id == 8888


@pytest.mark.asyncio
async def test_edit_skips_when_no_message_id():
    """Test edit skips when order has no channel_message_id."""
    order = Order(
        id=8,
        title="No Message ID",
        content="No channel message to edit",
        amount=None,
        status=OrderStatus.NEW,
        created_by=888,
        created_by_username="nomsg", 
        channel_message_id=None  # No message to edit
    )
    
    # Should return early without network calls
    await channel_publisher.edit_order_message(order)
    # No assertions needed - just verifying no exceptions raised