from itertools import count
from typing import Literal

from nonebot import get_adapter
from nonebot.adapters.onebot.v11 import Adapter, Bot, Message, MessageSegment
from nonebug import App

SENDER_ID = 10001
TARGET_ID = 10002
RESOURCE = "tetris.TETRIO.mask.list"
ROLE = "group:test-inherit"

_message_ids = count(1)


def make_group_event(group_id: int, user_id: int, message: Message):
    from nonebot.adapters.onebot.v11 import GroupMessageEvent
    from nonebot.adapters.onebot.v11.event import Sender
    from pydantic import create_model

    fake = create_model("_fake", __base__=GroupMessageEvent)

    class FakeEvent(fake):
        time: int = 1700000000
        self_id: int = 10000
        post_type: Literal["message"] = "message"
        sub_type: str = "normal"
        user_id: int = 1
        message_type: Literal["group"] = "group"
        group_id: int = 1
        message: Message = Message("test")
        original_message: Message = Message("test")
        raw_message: str = "test"
        font: int = 0
        sender: Sender = Sender(card="", nickname="user", role="member")
        to_me: bool = False

    return FakeEvent(
        message_id=next(_message_ids),
        group_id=group_id,
        user_id=user_id,
        message=message,
        original_message=message,
        raw_message=message.extract_plain_text(),
    )


def command_message(argument: str) -> Message:
    return Message(
        [
            MessageSegment.text("/permission user "),
            MessageSegment.at(TARGET_ID),
            MessageSegment.text(f" {argument}"),
        ]
    )


async def prepare():
    """准备发送者与目标用户，发送者拥有管理测试资源的权限"""
    from arclet.cithun import Permission
    from nonebot_plugin_uninfo import SupportScope
    from nonebot_plugin_user import get_user

    from nonebot_plugin_permission import SUPER_USER, system

    await system.define(RESOURCE)
    sender = await get_user(SupportScope.qq_client, str(SENDER_ID))
    sender_owner = await system.get_or_create_user(f"user:{sender.id}", sender.name)
    await system.inherit(sender_owner, SUPER_USER)
    await system.suset(sender_owner, "tetris.TETRIO.mask", Permission("vma"))
    await system.suset(sender_owner, RESOURCE, Permission("vma"))

    target = await get_user(SupportScope.qq_client, str(TARGET_ID))
    target_owner = await system.get_or_create_user(f"user:{target.id}", target.name)
    return sender_owner, target_owner


def expect_group_info(ctx, group_id: int):
    ctx.should_call_api("get_group_info", {"group_id": group_id}, {"group_id": group_id, "group_name": "test"})
    ctx.should_call_api(
        "get_group_member_info",
        {"group_id": group_id, "user_id": SENDER_ID, "no_cache": True},
        {"user_id": SENDER_ID, "nickname": "sender", "card": "", "role": "member", "sex": "unknown"},
    )


async def test_set_permission_for_mentioned_user(app: App):
    from arclet.cithun import Permission

    from nonebot_plugin_permission import system
    from nonebot_plugin_permission.command import perm

    group_id = 20001
    sender_owner, target_owner = await prepare()

    async with app.test_matcher(perm) as ctx:
        adapter = get_adapter(Adapter)
        bot = ctx.create_bot(base=Bot, adapter=adapter, self_id="10000")
        event = make_group_event(group_id, SENDER_ID, command_message(f"set {RESOURCE} true"))
        ctx.receive_event(bot, event)
        expect_group_info(ctx, group_id)
        ctx.should_call_send(event, f"Permission {RESOURCE} enabled for {target_owner.name}")

    target_acl = await system.get_acl(target_owner, RESOURCE)
    assert target_acl is not None
    assert target_acl.allow_mask == Permission("v-a")

    sender_acl = await system.get_acl(sender_owner, RESOURCE)
    assert sender_acl is not None
    assert sender_acl.allow_mask == Permission("vma")


async def test_get_permission_for_mentioned_user(app: App):
    from arclet.cithun import Permission

    from nonebot_plugin_permission import system
    from nonebot_plugin_permission.command import perm

    group_id = 20002
    _, target_owner = await prepare()
    await system.suset(target_owner, RESOURCE, Permission("v"))

    async with app.test_matcher(perm) as ctx:
        adapter = get_adapter(Adapter)
        bot = ctx.create_bot(base=Bot, adapter=adapter, self_id="10000")
        event = make_group_event(group_id, SENDER_ID, command_message(f"get {RESOURCE}"))
        ctx.receive_event(bot, event)
        expect_group_info(ctx, group_id)
        ctx.should_call_send(event, f"Permission {RESOURCE} for {target_owner.name} is {Permission('v')!r}")


async def test_inherit_for_mentioned_user(app: App):
    from nonebot_plugin_permission import system
    from nonebot_plugin_permission.command import perm

    group_id = 20003
    sender_owner, target_owner = await prepare()
    await system.create_role(ROLE, "TestInherit")

    async with app.test_matcher(perm) as ctx:
        adapter = get_adapter(Adapter)
        bot = ctx.create_bot(base=Bot, adapter=adapter, self_id="10000")
        event = make_group_event(group_id, SENDER_ID, command_message(f"inherit {ROLE}"))
        ctx.receive_event(bot, event)
        expect_group_info(ctx, group_id)
        ctx.should_call_send(event, f"{target_owner.name} inherit {ROLE} success")

    assert ROLE in target_owner.role_ids
    assert ROLE not in sender_owner.role_ids
