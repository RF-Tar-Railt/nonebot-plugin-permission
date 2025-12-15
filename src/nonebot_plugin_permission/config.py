from pydantic import BaseModel


class Config(BaseModel):
    permission_load_command: bool = True
    """是否加载权限命令"""

    permission_superusers: set[str] = set()
    """超级用户列表，以 `user` 插件绑定的用户id为准"""
