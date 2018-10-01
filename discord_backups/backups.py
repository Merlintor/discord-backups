import discord


class BackupSaver:
    def __init__(self, bot):
        self.bot = bot
        self.data = {}
        self.guild = None

    async def _save_channels(self):
        for channel in self.guild.channels:
            channel_data = {
                "name": channel.name,
                "position": channel.position,
                "category": None if channel.category is None else channel.category.id,
                "id": channel.id,
                "overwrites": [{
                    str(union.id): overwrite._values
                } for union, overwrite in channel.overwrites]
            }

            if isinstance(channel, discord.TextChannel):
                channel_data.update({
                    "type": "text",
                    "topic": channel.topic,
                    # "slowmode_delay": channel.slowmode_delay,
                    "nsfw": channel.is_nsfw(),
                    "messages": [{
                        "id": message.id,
                        "system_content": message.system_content,
                        "content": message.clean_content,
                        "author": message.author.id,
                        "pinned": message.pinned,
                        "attachments": [attach.url for attach in message.attachments],
                        "embed": [embed.to_dict() for embed in message.embeds],
                        "reactions": [
                            str(reaction.emoji.name)
                            if isinstance(reaction.emoji, discord.Emoji) else str(reaction.emoji)
                            for reaction in message.reactions
                        ],

                    } async for message in channel.history(limit=100, reverse=True)],

                    "webhooks": [{
                        "channel": webhook.channel.id,
                        "name": webhook.name,
                        "avatar": webhook.avatar_url,
                        "url": webhook.url

                    } for webhook in await channel.webhooks()]
                })

                self.data["text_channels"].append(channel_data)

            elif isinstance(channel, discord.VoiceChannel):
                channel_data.update({
                    "type": "voice",
                    "bitrate": channel.bitrate,
                    "user_limit": channel.user_limit,
                })

                self.data["voice_channels"].append(channel_data)

            if isinstance(channel, discord.CategoryChannel):
                channel_data.update({
                    "type": "category",
                })

                self.data["categories"].append(channel_data)

        self.data["text_channels"] = sorted(self.data["text_channels"], key=lambda c: c["position"])
        self.data["voice_channels"] = sorted(self.data["voice_channels"], key=lambda c: c["position"])
        self.data["categories"] = sorted(self.data["categories"], key=lambda c: c["position"])

    async def _save_roles(self):
        for role in self.guild.roles:
            if role.managed or role.is_default():
                continue

            role_data = {
                "id": role.id,
                "name": role.name,
                "permissions": role.permissions.value,
                "color": role.color.value,
                "hoist": role.hoist,
                "position": role.position,
                "mentionable": role.mentionable
            }

            self.data["roles"].append(role_data)

    async def _save_members(self):
        for member in self.guild.members:
            member_data = {
                "id": member.id,
                "name": member.name,
                "nick": member.nick,
                "roles": [role.id for role in member.roles[1:]]
            }

            self.data["members"].append(member_data)

    async def _save_bans(self):
        for user, reason in await self.guild.bans():
            ban_data = {
                "user": user,
                "reason": reason
            }

            self.data["bans"].append(ban_data)

    async def save_guild(self, guild, creator):
        self.guild = guild
        self.data = {
            "creator": creator.id,
            "id": self.guild.id,
            "name": self.guild.name,
            "owner": self.guild.owner.id,
            "region": str(self.guild.region),
            "afk_timeout": self.guild.afk_timeout,
            "afk_channel": None if self.guild.afk_channel is None else self.guild.afk_channel.id,
            "mfa_level": self.guild.mfa_level,
            "verification_level": str(self.guild.verification_level),
            "explicit_content_filter": str(self.guild.explicit_content_filter),
            "large": self.guild.large,

            "text_channels": [],
            "voice_channels": [],
            "categories": [],
            "roles": [],
            "members": [],
            "bans": []
        }

        await self._save_channels()
        await self._save_roles()
        await self._save_members()
        await self._save_bans()


class BackupLoader:
    def __init__(self, bot):
        self.bot = bot

    async def _clear_guild(self):
        for role in self.guild.roles:
            if role.managed or role.is_default():
                continue

            await role.delete()

        for channel in self.guild.channels:
            await channel.delete()

    async def load_backup(self, data, guild, hard=False, **options):
        self.guild = guild
        self.data = data

        if hard:
            await self._clear_guild()


class Backup(BackupLoader, BackupSaver):
    def __init__(self, bot, guild=None, creator=None, data=None):
        if data is None or (creator is None and guild is None):
            raise ValueError

        self.bot = bot
        self.data = None
        self.guild = guild
        self.data = data

        super().__init__(bot)

    @classmethod
    async def from_data(cls, bot, data):
        instance = cls(bot, data=data)
        return instance

    @classmethod
    async def from_guild(cls, bot, guild, creator=None):
        instance = cls(bot, guild=guild, creator=creator)
        await instance.save_guild(guild, creator)
        return instance

    async def load(self, guild):
        await self.load_backup(self.data, self.guild)

    @property
    def json(self):
        return self.data

    def to_json(self):
        return self.data