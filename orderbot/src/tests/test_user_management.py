import pytest
import os
import tempfile
from unittest.mock import AsyncMock, patch, mock_open
from aiogram.exceptions import TelegramBadRequest

from ..services.user_management import UserManagementService
from ..config import Settings


class TestUserManagementService:
    """用户管理服务测试"""
    
    @pytest.fixture
    def mock_settings(self, monkeypatch):
        """创建模拟的设置对象"""
        monkeypatch.setenv("ALLOWED_USER_IDS", "123,456")
        return Settings()
    
    @pytest.fixture
    def user_mgmt(self, mock_settings):
        """创建用户管理服务实例"""
        return UserManagementService(mock_settings)
    
    def test_is_admin_existing_user(self, user_mgmt):
        """测试检查现有管理员"""
        assert user_mgmt.is_admin(123) is True
        assert user_mgmt.is_admin(456) is True
    
    def test_is_admin_non_existing_user(self, user_mgmt):
        """测试检查非管理员用户"""
        assert user_mgmt.is_admin(789) is False
    
    def test_get_whitelist_users(self, user_mgmt):
        """测试获取白名单用户列表"""
        users = user_mgmt.get_whitelist_users()
        assert users == {123, 456}
    
    @pytest.mark.asyncio
    async def test_add_user_to_whitelist_new_user(self, user_mgmt, monkeypatch):
        """测试添加新用户到白名单"""
        # 模拟文件操作
        mock_file_content = 'ALLOWED_USER_IDS="123,456"\n'
        
        with patch("builtins.open", mock_open(read_data=mock_file_content)) as mock_file:
            with patch.dict(os.environ, {"ALLOWED_USER_IDS": "123,456"}):
                # 重新创建 settings 以反映环境变量
                user_mgmt.settings = Settings()
                
                result = await user_mgmt.add_user_to_whitelist(789)
                
                assert result is True
                # 验证文件写入被调用
                mock_file.assert_called()
    
    @pytest.mark.asyncio
    async def test_add_user_to_whitelist_existing_user(self, user_mgmt):
        """测试添加已存在的用户到白名单"""
        result = await user_mgmt.add_user_to_whitelist(123)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_resolve_username_to_id_success(self, user_mgmt):
        """测试成功解析用户名到用户ID"""
        mock_bot = AsyncMock()
        mock_chat = AsyncMock()
        mock_chat.id = 12345
        mock_bot.get_chat.return_value = mock_chat
        
        result = await user_mgmt.resolve_username_to_id(mock_bot, "@testuser")
        
        assert result == 12345
        mock_bot.get_chat.assert_called_once_with("@testuser")
    
    @pytest.mark.asyncio
    async def test_resolve_username_to_id_not_found(self, user_mgmt):
        """测试解析不存在的用户名"""
        mock_bot = AsyncMock()
        mock_bot.get_chat.side_effect = TelegramBadRequest(method="get_chat", message="User not found")
        
        result = await user_mgmt.resolve_username_to_id(mock_bot, "@nonexistent")
        
        assert result is None
        mock_bot.get_chat.assert_called_once_with("@nonexistent")
    
    @pytest.mark.asyncio
    async def test_resolve_username_to_id_without_at_symbol(self, user_mgmt):
        """测试解析不带@符号的用户名"""
        mock_bot = AsyncMock()
        mock_chat = AsyncMock()
        mock_chat.id = 54321
        mock_bot.get_chat.return_value = mock_chat
        
        result = await user_mgmt.resolve_username_to_id(mock_bot, "testuser")
        
        assert result == 54321
        mock_bot.get_chat.assert_called_once_with("@testuser")
    
    @pytest.mark.asyncio
    async def test_update_env_file_existing_key(self, user_mgmt):
        """测试更新现有环境变量键"""
        mock_content = 'BOT_TOKEN="test"\nALLOWED_USER_IDS="123,456"\nOTHER_VAR="value"\n'
        expected_content = 'BOT_TOKEN="test"\nALLOWED_USER_IDS="123,456,789"\nOTHER_VAR="value"\n'
        
        with patch("builtins.open", mock_open(read_data=mock_content)) as mock_file:
            await user_mgmt._update_env_file("ALLOWED_USER_IDS", "123,456,789")
            
            # 验证文件被正确写入
            handle = mock_file()
            written_content = "".join(call.args[0] for call in handle.write.call_args_list)
            assert "ALLOWED_USER_IDS=\"123,456,789\"" in written_content
    
    @pytest.mark.asyncio
    async def test_update_env_file_new_key(self, user_mgmt):
        """测试添加新的环境变量键"""
        mock_content = 'BOT_TOKEN="test"\n'
        
        with patch("builtins.open", mock_open(read_data=mock_content)) as mock_file:
            await user_mgmt._update_env_file("NEW_VAR", "new_value")
            
            # 验证新键被添加
            handle = mock_file()
            written_content = "".join(call.args[0] for call in handle.write.call_args_list)
            assert 'NEW_VAR="new_value"' in written_content
    
    @pytest.mark.asyncio
    async def test_update_env_file_nonexistent_file(self, user_mgmt):
        """测试更新不存在的环境变量文件"""
        with patch("builtins.open", mock_open()) as mock_file:
            # 模拟文件不存在的情况
            mock_file.side_effect = [FileNotFoundError(), mock_open().return_value]
            
            await user_mgmt._update_env_file("NEW_VAR", "new_value")
            
            # 验证文件被创建并写入
            assert mock_file.call_count >= 1