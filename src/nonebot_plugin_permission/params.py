from typing import Annotated

from nonebot.adapters import Event
from nonebot.params import Depends

from .model import Owner
from .monitor import monitor


async def get_user_owner(event: Event) -> Owner:
    user_id = event.get_user_id()
    user = await monitor.get_or_new_owner(f"user:{user_id}")
    return user


UserOwner = Annotated[Owner, Depends(get_user_owner)]
