import discord
import aiohttp


class BackupSaver():
    def __init__(self, guild):
        self.guild = guild
        self.data = {}

    def _overwrites_to_json(self, overwrites):
        return {overwrite[0].id: overwrite[1]._values for overwrite in overwrites}

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
                    "author": message.author.id,
                    "pinned": message.pinned,
                    "attachments": [attach.url for attach in message.attachments],
                    "embed": [embed.to_dict() for embed in message.embeds],
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
            if role.manages:
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
                "nick": member.nick,
                "roles": [role.id for role in member.roles[1:]]
            })

    async def _save_bans(self):
        for user, reason in await self.guild.bans():
            self.data["bans"].append({
                "user": user,
                "reason": reason
            })

    async def save(self, creator, chatlog=100):
        self.data = {
            "creator": creator.id,
            "id": self.guild.id,
            "name": self.guild.name,
            "owner": self.guild.owner.id,
            "member_count": self.guild.member_count,
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
            "bans": [],
        }

        await self._save_roles()
        await self._save_channels()
        await self._save_members()
        await self._save_bans()

    def __dict__(self):
        return self.data


class BackupLoader:
    def __init__(self, data, bot):
        self.data = data
        self.bot = bot
        self.id_translator = {}

    def overwrites_from_json(self, json):
        overwrites = {}
        for union_id, overwrite in json.items():
            union = self.guild.get_member(union_id)
            if union is None:
                roles = list(filter(lambda r: r.id == self.id_translator.get(union_id), self.guild.roles))
                if len(roles) == 0:
                    continue

                union = roles[0]

            overwrites[union] = discord.PermissionOverwrite(**overwrite)

        return overwrites

    async def _prepare_guild(self):
        if self.options.get("roles"):
            for role in self.guild.roles:
                if not role.managed and not role.is_default():
                    await role.delete(reasone=self.reason)

        if self.options.get("channels"):
            for channel in self.guild.channels:
                await channel.dete(reason=self.reason)

    async def _load_roles(self):
        for role in self.data["roles"]:
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
                overwrites=self.overwrites_from_json(category["overwrites"])
            )
            self.id_translator[category["id"]] = created.id

    async def _load_text_channels(self):
        for tchannel in self.data["text_channels"]:
            created = await self.guild.create_text_channel(
                name=tchannel["name"],
                overwrites=self.overwrites_from_json(tchannel["overwrites"]),
                category=discord.Object(self.id_translator.get(tchannel["category"]))
            )
            await created.edit(
                topic=tchannel["topic"],
                nsfw=tchannel["nsfw"],
            )
            self.id_translator[tchannel["id"]] = created.id

    async def _load_voice_channels(self):
        for vchannel in self.data["voice_channels"]:
            created = await self.guild.create_voice_channel(
                name=vchannel["name"],
                overwrites=self.overwrites_from_json(vchannel["overwrites"]),
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

    async def _load_member_list(self):
        session = aiohttp.ClientSession(loop=self.bot.loop)
        async with session.post(
            url="https://api.paste.ee/v1/pastes",
            headers={"X-Auth-Token": "a33dENSQIZdOdjuHkloI3aB20lsZV4Tlk9qBFD8f5"},
            json={
                "encrypted": True,
                "description": f"Members of '{self.data['name']}'",
                "sections": [
                    {
                        "name": "Members",
                        "contents": "\n".join(
                            [f"{member['name']}:\n"
                             f"   Nick: {member['nick']}\n"
                             f"   Roles: \n"
                             f"   Id: {member['id']}" for member in sorted(self.data["members"], key=lambda m: len(member['roles']), reverse=True)]
                        )
                    }
                ]
            }
        ) as response:
            return response


    async def load(self, guild, loader: discord.User, chatlog, **options):
        self.guild = guild
        self.options = options
        self.loader = loader
        self.reason = f"Backup loaded by {loader}"
