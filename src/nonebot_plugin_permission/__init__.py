from nonebot import get_driver, get_plugin_config, load_plugin, require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_orm")
require("nonebot_plugin_user")

from . import migrations
from .checker import depends_permission as depends_permission
from .checker import require_permission as require_permission
from .config import Config
from .main import system as system
from .params import UserOwner as UserOwner

driver = get_driver()
_config = get_plugin_config(Config)

__version__ = "0.1.0"
__plugin_meta__ = PluginMetadata(
    name="Permission",
    description="权限实现",
    usage="",
    homepage="https://github.com/RF-Tar-Railt/nonebot-plugin-permission",
    type="application",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_orm"),
    extra={"author": "RF-Tar-Railt", "priority": 3, "version": __version__, "orm_version_location": migrations},
)


SUPER_USER = system.pre_role("SUPER_USER", "super_user")


@driver.on_startup
async def on_startup():
    await system.load()
    superusers = _config.permission_superusers
    for user in superusers:
        user = await system.get_or_create_user(f"user:{user}", user)
        await system.inherit(user, SUPER_USER)


if _config.permission_load_command:
    load_plugin("nonebot_plugin_permission.command")
