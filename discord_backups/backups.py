import discord
import time
from datetime import datetime

from . import utils


class BackupSaver():
    def __init__(self, bot, session, guild):
        self.session = session
        self.bot = bot
        self.guild = guild
        self.data = {}

    def _overwrites_to_json(self, overwrites):
        return {str(overwrite[0].id): overwrite[1]._values for overwrite in overwrites}

    async def _save_channels(self):
        for category in self.guild.categories:
            self.data["categories"].append({
                "name": category.name,
                "position": category.position,
                "category": None if category.category is None else category.category.id,
                "id": category.id,
                "overwrites": self._overwrites_to_json(category.overwrites)
            })

        for tchannel in self.guild.text_channels:
            self.data["text_channels"].append({
                "name": tchannel.name,
                "position": tchannel.position,
                "category": None if tchannel.category is None else tchannel.category.id,
                "id": tchannel.id,
                "overwrites": self._overwrites_to_json(tchannel.overwrites),
                "topic": tchannel.topic,
                "slowmode_delay": tchannel.slowmode_delay,
                "nsfw": tchannel.is_nsfw(),
                "messages": [{
                    "id": message.id,
                    "content": message.system_content,
                    "author": {
                        "id": message.author.id,
                        "name": message.author.name,
                        "discriminator": message.author.discriminator,
                        "avatar_url": message.author.avatar_url
                    },
                    "pinned": message.pinned,
                    "attachments": [attach.url for attach in message.attachments],
                    "embeds": [embed.to_dict() for embed in message.embeds],
                    "reactions": [
                        str(reaction.emoji.name)
                        if isinstance(reaction.emoji, discord.Emoji) else str(reaction.emoji)
                        for reaction in message.reactions
                    ],

                } async for message in tchannel.history(limit=100, reverse=True)],

                "webhooks": [{
                    "channel": webhook.channel.id,
                    "name": webhook.name,
                    "avatar": webhook.avatar_url,
                    "url": webhook.url

                } for webhook in await tchannel.webhooks()]
            })

        for vchannel in self.guild.voice_channels:
            self.data["voice_channels"].append({
                "name": vchannel.name,
                "position": vchannel.position,
                "category": None if vchannel.category is None else vchannel.category.id,
                "id": vchannel.id,
                "overwrites": self._overwrites_to_json(vchannel.overwrites),
                "bitrate": vchannel.bitrate,
                "user_limit": vchannel.user_limit,
            })

    async def _save_roles(self):
        for role in self.guild.roles:
            if role.managed:
                continue

            self.data["roles"].append({
                "id": role.id,
                "default": role.is_default(),
                "name": role.name,
                "permissions": role.permissions.value,
                "color": role.color.value,
                "hoist": role.hoist,
                "position": role.position,
                "mentionable": role.mentionable
            })

    async def _save_members(self):
        for member in self.guild.members:
            self.data["members"].append({
                "id": member.id,
                "name": member.name,
                "discriminator": member.discriminator,
                "nick": member.nick,
                "roles": [role.id for role in member.roles[1:]]
            })

    async def _save_bans(self):
        for user, reason in await self.guild.bans():
            try:
                self.data["bans"].append({
                    "user": user.id,
                    "reason": reason
                })
            except:
                # User probably doesn't exist anymore
                pass

    async def _paste(self):
        """Should be the last thing that gets saved"""
        async with self.session.post(
                url="https://api.paste.ee/v1/pastes",
                headers={"X-Auth-Token": "uwvWc7GW1b1iLAMiaWZZTGCcJgN8OPu7usWoM97rB"},
                json={
                    "encrypted": True,
                    "description": f"Members of '{self.data['name']}' (Only members with roles are listed)",
                    "sections": [
                        {
                            "name": "Members",
                            "contents": "\n".join(
                                [f"{member.name}:\n"
                                 f"   Nick: {member.nick}\n"
                                 f"   Roles: {', '.join([role.name for role in member.roles[1:]])}\n"
                                 f"   Id: {member.id}\n" for member in
                                 sorted(self.guild.members, key=lambda m: len(m.roles), reverse=True)
                                 if not member.bot if len(member.roles) > 1]
                            )
                        },
                        {
                            "name": "Bots",
                            "contents": "\n".join(
                                [f"{bot.name}:\n"
                                 f"   Nick: {bot.nick}\n"
                                 f"   Roles: {', '.join([role.name for role in bot.roles[1:]])}\n"
                                 f"   Id: {bot.id}\n"
                                 f"   Invite: https://discordapp.com/api/oauth2/authorize?client_id={bot.id}"
                                 f"&permissions={bot.guild_permissions.value}&scope=bot\n" for bot in self.guild.members
                                 if bot.bot if len(bot.roles) > 1]
                            )
                        }
                    ]
                }
        ) as response:
            self.data["paste"] = (await response.json()).get("link")

    async def save(self, creator, chatlog=100):
        self.data = {
            "version": 0.2,
            "timestamp": time.mktime(datetime.utcnow().timetuple()),
            "creator": creator.id,
            "id": self.guild.id,
            "name": self.guild.name,
            "icon_url": self.guild.icon_url,
            "owner": self.guild.owner.id,
            "member_count": self.guild.member_count,
            "region": str(self.guild.region),
            "afk_timeout": self.guild.afk_timeout,
            "afk_channel": None if self.guild.afk_channel is None else self.guild.afk_channel.id,
            "mfa_level": self.guild.mfa_level,
            "verification_level": str(self.guild.verification_level),
            "explicit_content_filter": str(self.guild.explicit_content_filter),
            "large": self.guild.large,

            "paste": "",

            "text_channels": [],
            "voice_channels": [],
            "categories": [],
            "roles": [],
            "members": [],
            "bans": [],
        }

        await self._save_roles()
        await self._save_channels()
        await self._save_members()
        await self._save_bans()
        await self._paste()

        return self.data

    def __dict__(self):
        return self.data


class BackupLoader:
    def __init__(self, bot, session, data):
        self.session = session
        self.data = data
        self.bot = bot
        self.id_translator = {}
        self.options = {"channels": True, "roles": True}


    def _overwrites_from_json(self, json):
        overwrites = {}
        for union_id, overwrite in json.items():
            union = self.guild.get_member(union_id)
            if union is None:
                roles = list(filter(lambda r: r.id == self.id_translator.get(int(union_id)), self.guild.roles))
                if len(roles) == 0:
                    continue

                union = roles[0]

            overwrites[union] = discord.PermissionOverwrite(**overwrite)

        return overwrites

    async def _prepare_guild(self):
        if self.options.get("roles"):
            for role in self.guild.roles:
                if not role.managed and not role.is_default():
                    await role.delete(reason=self.reason)

        if self.options.get("channels"):
            for channel in self.guild.channels:
                await channel.delete(reason=self.reason)

    async def _load_roles(self):
        for role in reversed(self.data["roles"]):
            if role["default"]:
                await self.guild.default_role.edit(
                    permissions=discord.Permissions(role["permissions"])
                )
                created = self.guild.default_role
            else:
                created = await self.guild.create_role(
                    name=role["name"],
                    hoist=role["hoist"],
                    mentionable=role["mentionable"],
                    color=discord.Color(role["color"]),
                    permissions=discord.Permissions(role["permissions"])
                )

            self.id_translator[role["id"]] = created.id

    async def _load_categories(self):
        for category in self.data["categories"]:
            created = await self.guild.create_category_channel(
                name=category["name"],
                overwrites=self._overwrites_from_json(category["overwrites"])
            )
            self.id_translator[category["id"]] = created.id

    async def _load_text_channels(self):
        for tchannel in self.data["text_channels"]:
            created = await self.guild.create_text_channel(
                name=tchannel["name"],
                overwrites=self._overwrites_from_json(tchannel["overwrites"]),
                category=discord.Object(self.id_translator.get(tchannel["category"]))
            )
            await created.edit(
                topic=tchannel["topic"],
                nsfw=tchannel["nsfw"],
            )

            webh = await created.create_webhook(name="chatlog")
            for message in tchannel["messages"][-self.chatlog:]:
                try:
                    await webh.send(
                        username=message["author"]["name"],
                        avatar_url=message["author"]["avatar_url"],
                        content=utils.clean_content(message["content"]),
                        embeds=[discord.Embed.from_data(embed) for embed in message["embeds"]]
                    )
                except:
                    # Content and embeds are probably empty
                    pass

            await webh.delete()

            self.id_translator[tchannel["id"]] = created.id

    async def _load_voice_channels(self):
        for vchannel in self.data["voice_channels"]:
            created = await self.guild.create_voice_channel(
                name=vchannel["name"],
                overwrites=self._overwrites_from_json(vchannel["overwrites"]),
                category=discord.Object(self.id_translator.get(vchannel["category"]))
            )
            await created.edit(
                bitrate=vchannel["bitrate"],
                user_limit=vchannel["user_limit"]
            )
            self.id_translator[vchannel["id"]] = created.id

    async def _load_channels(self):
        await self._load_categories()
        await self._load_text_channels()
        await self._load_voice_channels()

    async def _load_bans(self):
        for ban in self.data["bans"]:
            try:
                await self.guild.ban(user=discord.Object(ban["user"]), reason=ban["reason"])
            except:
                # User probably doesn't exist anymore (or is already banned?)
                pass

    async def load(self, guild, loader: discord.User, chatlog, **options):
        self.guild = guild
        self.chatlog = chatlog
        self.options.update(options)
        self.loader = loader
        self.reason = f"Backup loaded by {loader}"

        await self._prepare_guild()
        await self._load_roles()
        await self._load_channels()
        await self._load_bans()


class BackupInfo():
    def __init__(self, bot, data):
        self.bot = bot
        self.data = data

    @property
    def icon_url(self):
        return self.data["icon_url"]

    @property
    def name(self):
        return self.data["name"]

    def channels(self, limit=1000):
        ret = "```"
        for channel in self.data["text_channels"]:
            if channel.get("category") is None:
                ret += "\n#\u200a" + channel["name"]

        for channel in self.data["voice_channels"]:
            if channel.get("category") is None:
                ret += "\n \u200a" + channel["name"]

        ret += "\n"
        for category in self.data["categories"]:
            ret += "\n⯆\u200a" + category["name"]
            for channel in self.data["text_channels"]:
                if channel.get("category") == category["id"]:
                    ret += "\n  #\u200a" + channel["name"]

            for channel in self.data["voice_channels"]:
                if channel.get("category") == category["id"]:
                    ret += "\n   \u200a" + channel["name"]

            ret += "\n"

        return ret[:limit-10] + "```"

    def roles(self, limit=1000):
        ret = "```"
        for role in reversed(self.data["roles"]):
            ret += "\n" + role["name"]

        return ret[:limit-10] + "```"

    @property
    def member_count(self):
        return self.data["member_count"]

    @property
    def chatlog(self):
        max_messages = 0
        for channel in self.data["text_channels"]:
            if len(channel["messages"]) > max_messages:
                max_messages = len(channel["messages"])

        return max_messages

    @property
    def timestamp(self):
        return datetime.fromtimestamp(self.data["timestamp"])

    @property
    def creator(self):
        return self.data["creator"]

