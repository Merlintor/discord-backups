import discord

from . import utils


async def copy_guild(origin, target, chatlog=20):
    ids = {}

    def convert_overwrites(overwrites: list):
        ret = {}
        for union, overwrite in overwrites:
            if isinstance(union, discord.Role):
                role = target.get_role(ids.get(union.id))
                if role is not None:
                    ret[role] = overwrite

            elif isinstance(union, discord.Member):
                ret[union] = overwrite

        return ret

    for channel in target.channels:
        await channel.delete()

    for role in target.roles:
        if role.managed or role.is_default():
            continue

        await role.delete()

    for role in reversed(origin.roles):
        if role.managed:
            continue

        if role.is_default():
            created = target.default_role

        else:
            created = await target.create_role(
                name=role.name,
                hoist=role.hoist,
                mentionable=role.mentionable,
                color=role.color
            )

        await created.edit(
            permissions=role.permissions
        )
        ids[role.id] = created.id

    for category in origin.categories:
        created = await target.create_category(
            name=category.name,
            overwrites=convert_overwrites(category.overwrites),
        )
        ids[category.id] = created.id

    for channel in origin.text_channels:
        created = await target.create_text_channel(
            name=channel.name,
            overwrites=convert_overwrites(channel.overwrites),
            category=None if channel.category is None else target.get_channel(ids.get(channel.category.id))
        )
        await created.edit(
            topic=channel.topic,
            nsfw=channel.is_nsfw(),
            slowmode_delay=channel.slowmode_delay
        )
        webh = await created.create_webhook(
            name="sync"
        )
        async for message in channel.history(limit=chatlog, reverse=True):
            if message.system_content.replace(" ", "") == "" and len(message.embeds) == 0:
                continue

            await webh.send(
                username=message.author.name,
                avatar_url=message.author.avatar_url,
                content=utils.clean_content(message.system_content) + "\n".join([attach.url for attach in message.attachments]),
                embeds=message.embeds
            )

        await webh.delete()
        ids[channel.id] = created.id

    for vchannel in origin.voice_channels:
        created = await target.create_voice_channel(
            name=vchannel.name,
            overwrites=convert_overwrites(vchannel.overwrites),
            category=None if vchannel.category is None else target.get_channel(ids.get(vchannel.category.id))
        )
        await created.edit(
            bitrate=vchannel.bitrate,
            user_limit=vchannel.user_limit,
        )

    await target.edit(
        name=origin.name,
        region=origin.region,
        afk_channel=None if origin.afk_channel is None else target.get_channel(ids.get(origin.afk_channel.id)),
        afk_timeout=origin.afk_timeout,
        verification_level=origin.verification_level,
        system_channel=None if origin.system_channel is None else target.get_channel(ids.get(origin.system_channel.id)),
    )

    return ids