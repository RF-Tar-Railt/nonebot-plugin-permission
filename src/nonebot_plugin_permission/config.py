from pydantic import BaseModel


class Config(BaseModel):
    permission_load_command: bool = True
    """是否加载权限命令"""
