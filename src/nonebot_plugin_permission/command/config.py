from typing import Optional

from pydantic import BaseModel


class Config(BaseModel):
    """Plugin Config Here"""

    permission_command_start: Optional[set[str]] = None
    """插件使用的命令前缀，如果不填则使用全局命令前缀 (COMMAND_START)"""

    permission_command_name: str = "permission"
    """插件使用的帮助命令名称"""
