from typing import Annotated

from nonebot.adapters import Event
from nonebot.params import Depends
from nonebot_plugin_uninfo import Uninfo
from nonebot_plugin_user import get_user

from .model import Owner
from .monitor import monitor


async def get_user_owner(event: Event, sess: Uninfo) -> Owner:
    user_model = await get_user(sess.scope, sess.user.id)
    user = await monitor.get_or_new_owner(f"user:{user_model.id}")
    return user


UserOwner = Annotated[Owner, Depends(get_user_owner)]
