from __future__ import annotations

import os
from typing import Set, Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from ..config import Settings
from ..utils.logging import log_info, log_error


class UserManagementService:
    """用户管理服务，负责白名单用户的动态管理"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    async def add_user_to_whitelist(self, user_id: int) -> bool:
        """添加用户到白名单
        
        Args:
            user_id: 要添加的用户ID
            
        Returns:
            bool: 添加是否成功
        """
        current_ids = self.settings.allowed_user_ids()
        
        if user_id in current_ids:
            log_info("user.whitelist.already_exists", user_id=user_id)
            return False
        
        # 添加新用户ID
        current_ids.add(user_id)
        
        # 更新环境变量
        new_ids_str = ",".join(str(uid) for uid in sorted(current_ids))
        
        try:
            # 更新 .env 文件
            await self._update_env_file("ALLOWED_USER_IDS", new_ids_str)
            
            # 更新当前实例的环境变量
            os.environ["ALLOWED_USER_IDS"] = new_ids_str
            
            # 重新创建 settings 实例以反映更改
            self.settings = Settings()
            
            log_info("user.whitelist.added", user_id=user_id, total_users=len(current_ids))
            return True
            
        except Exception as e:
            log_error("user.whitelist.add_failed", user_id=user_id, error=str(e))
            return False
    
    async def remove_user_from_whitelist(self, user_id: int) -> bool:
        """从白名单中移除用户
        
        Args:
            user_id: 要移除的用户ID
            
        Returns:
            bool: 移除是否成功
        """
        current_ids = self.settings.allowed_user_ids()
        
        if user_id not in current_ids:
            log_info("user.whitelist.not_exists", user_id=user_id)
            return False
        
        # 移除用户ID
        current_ids.remove(user_id)
        
        # 更新环境变量
        new_ids_str = ",".join(str(uid) for uid in sorted(current_ids))
        
        try:
            # 更新 .env 文件
            await self._update_env_file("ALLOWED_USER_IDS", new_ids_str)
            
            # 更新当前实例的环境变量
            os.environ["ALLOWED_USER_IDS"] = new_ids_str
            
            # 重新创建 settings 实例以反映更改
            self.settings = Settings()
            
            log_info("user.whitelist.removed", user_id=user_id, total_users=len(current_ids))
            return True
            
        except Exception as e:
            log_error("user.whitelist.remove_failed", user_id=user_id, error=str(e))
            return False
    
    async def resolve_username_to_id(self, bot: Bot, username: str) -> Optional[int]:
        """通过用户名解析用户ID
        
        Args:
            bot: Telegram Bot 实例
            username: 用户名（可以包含或不包含@符号）
            
        Returns:
            Optional[int]: 用户ID，如果解析失败返回None
        """
        # 清理用户名格式
        clean_username = username.lstrip("@")
        
        try:
            # 尝试通过用户名获取用户信息
            # 注意：这个方法只对已经与机器人交互过的用户有效
            # 或者需要用户先发送消息给机器人
            chat = await bot.get_chat(f"@{clean_username}")
            if chat and chat.id:
                log_info("user.username.resolved", username=username, user_id=chat.id)
                return chat.id
        except TelegramBadRequest as e:
            log_error("user.username.resolve_failed", username=username, error=str(e))
        except Exception as e:
            log_error("user.username.resolve_error", username=username, error=str(e))
        
        return None
    
    async def _update_env_file(self, key: str, value: str) -> None:
        """更新 .env 文件中的指定键值
        
        Args:
            key: 环境变量键名
            value: 环境变量值
        """
        env_file_path = ".env"
        
        # 读取现有的 .env 文件内容
        lines = []
        key_found = False
        
        try:
            with open(env_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            # 如果文件不存在，创建新文件
            pass
        
        # 更新或添加键值对
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f'{key}="{value}"\n'
                key_found = True
                break
        
        # 如果键不存在，添加到文件末尾
        if not key_found:
            lines.append(f'{key}="{value}"\n')
        
        # 写回文件
        with open(env_file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        
        log_info("env.file.updated", key=key, value=value)
    
    def is_admin(self, user_id: int) -> bool:
        """检查用户是否为管理员
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 是否为管理员
        """
        return user_id in self.settings.allowed_user_ids()
    
    def get_whitelist_users(self) -> Set[int]:
        """获取当前白名单用户列表
        
        Returns:
            Set[int]: 白名单用户ID集合
        """
        return self.settings.allowed_user_ids()
    
    async def add_operator(self, user_id: int) -> bool:
        """添加操作人（add_user_to_whitelist的别名）
        
        Args:
            user_id: 要添加的用户ID
            
        Returns:
            bool: 添加是否成功
        """
        return await self.add_user_to_whitelist(user_id)
    
    async def remove_operator(self, user_id: int) -> bool:
        """移除操作人（remove_user_from_whitelist的别名）
        
        Args:
            user_id: 要移除的用户ID
            
        Returns:
            bool: 移除是否成功
        """
        return await self.remove_user_from_whitelist(user_id)
    
    async def get_operators(self) -> Set[int]:
        """获取操作人列表（get_whitelist_users的异步别名）
        
        Returns:
            Set[int]: 操作人用户ID集合
        """
        return self.get_whitelist_users()