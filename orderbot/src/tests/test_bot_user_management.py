import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram import Bot
from aiogram.types import Message, User, Chat
from aiogram.exceptions import TelegramBadRequest

from ..tg.bot import cmd_add_operator, cmd_list_operators
from ..services.user_management import UserManagementService
from ..config import Settings


class TestBotUserManagement:
    """机器人用户管理命令测试"""
    
    @pytest.fixture
    def mock_settings(self, monkeypatch):
        """创建模拟的设置对象"""
        monkeypatch.setenv("ALLOWED_USER_IDS", "123")
        return Settings()
    
    @pytest.fixture
    def mock_user_mgmt(self, mock_settings):
        """创建模拟的用户管理服务"""
        return UserManagementService(mock_settings)
    
    @pytest.fixture
    def mock_admin_user(self):
        """创建模拟的管理员用户"""
        return User(id=123, is_bot=False, first_name="Admin")
    
    @pytest.fixture
    def mock_regular_user(self):
        """创建模拟的普通用户"""
        return User(id=456, is_bot=False, first_name="User")
    
    @pytest.fixture
    def mock_chat(self):
        """创建模拟的聊天对象"""
        return Chat(id=123, type="private")
    
    @pytest.mark.asyncio
    async def test_add_operator_success_with_username(self, mock_user_mgmt, mock_admin_user, mock_chat):
        """测试管理员成功通过用户名添加操作人"""
        # 创建模拟消息
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_admin_user,
            text="/添加操作人 @newuser"
        )
        message.answer = AsyncMock()
        
        # 模拟 Bot 实例
        mock_bot = AsyncMock(spec=Bot)
        message.bot = mock_bot
        
        with patch('orderbot.src.tg.bot.user_mgmt', mock_user_mgmt):
            with patch('orderbot.src.tg.bot.settings', mock_user_mgmt.settings):
                # 模拟用户管理服务方法
                mock_user_mgmt.is_admin = MagicMock(return_value=True)
                mock_user_mgmt.resolve_username_to_id = AsyncMock(return_value=789)
                mock_user_mgmt.add_user_to_whitelist = AsyncMock(return_value=True)
                mock_user_mgmt.get_whitelist_users = MagicMock(return_value={123, 789})
                
                await cmd_add_operator(message)
                
                # 验证调用
                mock_user_mgmt.is_admin.assert_called_once_with(123)
                mock_user_mgmt.resolve_username_to_id.assert_called_once_with(mock_bot, "@newuser")
                mock_user_mgmt.add_user_to_whitelist.assert_called_once_with(789)
                
                # 验证成功消息
                message.answer.assert_called_once()
                call_args = message.answer.call_args[0][0]
                assert "✅ 成功添加操作人" in call_args
                assert "用户ID: 789" in call_args
    
    @pytest.mark.asyncio
    async def test_add_operator_success_with_user_id(self, mock_user_mgmt, mock_admin_user, mock_chat):
        """测试管理员成功通过用户ID添加操作人"""
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_admin_user,
            text="/添加操作人 789"
        )
        message.answer = AsyncMock()
        
        with patch('orderbot.src.tg.bot.user_mgmt', mock_user_mgmt):
            with patch('orderbot.src.tg.bot.settings', mock_user_mgmt.settings):
                mock_user_mgmt.is_admin = MagicMock(return_value=True)
                mock_user_mgmt.add_user_to_whitelist = AsyncMock(return_value=True)
                mock_user_mgmt.get_whitelist_users = MagicMock(return_value={123, 789})
                
                await cmd_add_operator(message)
                
                # 验证调用
                mock_user_mgmt.is_admin.assert_called_once_with(123)
                mock_user_mgmt.add_user_to_whitelist.assert_called_once_with(789)
                
                # 验证成功消息
                message.answer.assert_called_once()
                call_args = message.answer.call_args[0][0]
                assert "✅ 成功添加操作人" in call_args
    
    @pytest.mark.asyncio
    async def test_add_operator_permission_denied(self, mock_user_mgmt, mock_regular_user, mock_chat):
        """测试非管理员用户被拒绝添加操作人"""
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_regular_user,
            text="/添加操作人 @newuser"
        )
        message.answer = AsyncMock()
        
        with patch('orderbot.src.tg.bot.user_mgmt', mock_user_mgmt):
            mock_user_mgmt.is_admin = MagicMock(return_value=False)
            
            await cmd_add_operator(message)
            
            # 验证权限检查
            mock_user_mgmt.is_admin.assert_called_once_with(456)
            
            # 验证错误消息
            message.answer.assert_called_once_with("❌ 您没有权限执行此操作。只有管理员可以添加操作人。")
    
    @pytest.mark.asyncio
    async def test_add_operator_user_already_exists(self, mock_user_mgmt, mock_admin_user, mock_chat):
        """测试添加已存在的操作人"""
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_admin_user,
            text="/添加操作人 123"
        )
        message.answer = AsyncMock()
        
        with patch('orderbot.src.tg.bot.user_mgmt', mock_user_mgmt):
            with patch('orderbot.src.tg.bot.settings', mock_user_mgmt.settings):
                mock_user_mgmt.is_admin = MagicMock(return_value=True)
                mock_user_mgmt.add_user_to_whitelist = AsyncMock(return_value=False)
                
                await cmd_add_operator(message)
                
                # 验证错误消息
                message.answer.assert_called_once_with("⚠️ 用户 123 已经是操作人了。")
    
    @pytest.mark.asyncio
    async def test_add_operator_username_not_found(self, mock_user_mgmt, mock_admin_user, mock_chat):
        """测试用户名不存在的情况"""
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_admin_user,
            text="/添加操作人 @nonexistent"
        )
        message.answer = AsyncMock()
        message.bot = AsyncMock(spec=Bot)
        
        with patch('orderbot.src.tg.bot.user_mgmt', mock_user_mgmt):
            mock_user_mgmt.is_admin = MagicMock(return_value=True)
            mock_user_mgmt.resolve_username_to_id = AsyncMock(return_value=None)
            
            await cmd_add_operator(message)
            
            # 验证错误消息
            message.answer.assert_called_once_with("❌ 找不到用户 @nonexistent，请检查用户名是否正确。")
    
    @pytest.mark.asyncio
    async def test_add_operator_invalid_format(self, mock_user_mgmt, mock_admin_user, mock_chat):
        """测试无效的命令格式"""
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_admin_user,
            text="/添加操作人"
        )
        message.answer = AsyncMock()
        
        with patch('orderbot.src.tg.bot.user_mgmt', mock_user_mgmt):
            mock_user_mgmt.is_admin = MagicMock(return_value=True)
            
            await cmd_add_operator(message)
            
            # 验证错误消息
            message.answer.assert_called_once()
            call_args = message.answer.call_args[0][0]
            assert "❌ 请提供要添加的用户名或用户ID" in call_args
    
    @pytest.mark.asyncio
    async def test_list_operators_success(self, mock_user_mgmt, mock_admin_user, mock_chat):
        """测试管理员成功查看操作人列表"""
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_admin_user,
            text="/查看操作人"
        )
        message.answer = AsyncMock()
        
        with patch('orderbot.src.tg.bot.user_mgmt', mock_user_mgmt):
            mock_user_mgmt.is_admin = MagicMock(return_value=True)
            mock_user_mgmt.get_whitelist_users = MagicMock(return_value={123, 456, 789})
            
            await cmd_list_operators(message)
            
            # 验证调用
            mock_user_mgmt.is_admin.assert_called_once_with(123)
            mock_user_mgmt.get_whitelist_users.assert_called_once()
            
            # 验证响应消息
            message.answer.assert_called_once()
            call_args = message.answer.call_args[0][0]
            assert "📋 当前白名单操作人列表" in call_args
            assert "• 123" in call_args
            assert "• 456" in call_args
            assert "• 789" in call_args
            assert "总计: 3 人" in call_args
    
    @pytest.mark.asyncio
    async def test_list_operators_permission_denied(self, mock_user_mgmt, mock_regular_user, mock_chat):
        """测试非管理员用户被拒绝查看操作人列表"""
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_regular_user,
            text="/查看操作人"
        )
        message.answer = AsyncMock()
        
        with patch('orderbot.src.tg.bot.user_mgmt', mock_user_mgmt):
            mock_user_mgmt.is_admin = MagicMock(return_value=False)
            
            await cmd_list_operators(message)
            
            # 验证权限检查
            mock_user_mgmt.is_admin.assert_called_once_with(456)
            
            # 验证错误消息
            message.answer.assert_called_once_with("❌ 您没有权限执行此操作。只有管理员可以查看操作人列表。")
    
    @pytest.mark.asyncio
    async def test_list_operators_empty_list(self, mock_user_mgmt, mock_admin_user, mock_chat):
        """测试查看空的操作人列表"""
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_admin_user,
            text="/查看操作人"
        )
        message.answer = AsyncMock()
        
        with patch('orderbot.src.tg.bot.user_mgmt', mock_user_mgmt):
            mock_user_mgmt.is_admin = MagicMock(return_value=True)
            mock_user_mgmt.get_whitelist_users = MagicMock(return_value=set())
            
            await cmd_list_operators(message)
            
            # 验证响应消息
            message.answer.assert_called_once_with("📋 当前没有配置白名单用户。")