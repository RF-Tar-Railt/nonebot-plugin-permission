from typing import Annotated

from arclet.cithun import User
from nonebot.adapters import Event
from nonebot.params import Depends
from nonebot_plugin_uninfo import Uninfo
from nonebot_plugin_user import get_user

from .main import system


async def get_user_model(event: Event, sess: Uninfo) -> User:
    user_model = await get_user(sess.scope, sess.user.id)
    user = await system.get_or_create_user(str(user_model.id), user_model.name)
    return user


UserOwner = Annotated[User, Depends(get_user_model)]
