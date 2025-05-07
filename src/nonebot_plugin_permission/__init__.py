from arclet.cithun import NodeState as NodeState
from arclet.cithun import PE as PE
from arclet.cithun import ROOT as ROOT
from nonebot import get_driver, get_plugin_config, load_plugin, require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_orm")

from . import migrations
from .checker import depends_permission as depends_permission
from .checker import require_permission as require_permission
from .config import Config
from .monitor import monitor as monitor
from .params import UserOwner as UserOwner

driver = get_driver()
global_config = driver.config
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


SUPER_USER = monitor.predefine_owner("group:super_user", 0)


@driver.on_startup
async def on_startup():
    await monitor.load()
    superusers = global_config.superusers
    for user in superusers:
        user = await monitor.get_or_new_owner(f"user:{user}")
        await monitor.inherit(user, SUPER_USER)


@driver.on_shutdown
async def on_shutdown():
    await monitor.save()


if _config.permission_load_command:
    load_plugin("nonebot_plugin_permission.command")
