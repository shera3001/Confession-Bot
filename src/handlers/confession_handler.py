import os
import re
import json
from typing import Optional

import discord


CONFESSION_ID_RE = re.compile(r"#(\d+)")
MAX_ATTACHMENT_SIZE_BYTES = 500 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
class ConfessionModal(discord.ui.Modal):
    confession_content = discord.ui.TextInput(
        label="Confession Content",
        style=discord.TextStyle.paragraph,
        max_length=1800,
        required=True,
    )
    attachment_url = discord.ui.TextInput(
        label="Link Gambar (opsional)",
        style=discord.TextStyle.short,
        max_length=500,
        required=False,
        placeholder="Paste URL gambar (png/jpg/gif/webp)",
    )
    custom_color = discord.ui.TextInput(
        label="Warna Embed (opsional)",
        style=discord.TextStyle.short,
        max_length=32,
        required=False,
        placeholder="Contoh: ff0000, #ff0000, atau red",
    )

    def __init__(self, handler: "ConfessionHandler", mode: str, source_message_id: Optional[int] = None):
        super().__init__(title="Submit a Confession")
        self.handler = handler
        self.mode = mode
        self.source_message_id = source_message_id

    async def on_submit(self, interaction: discord.Interaction):
        content = str(self.confession_content).strip()
        custom_color = str(self.custom_color).strip() or None
        attachment_url = str(self.attachment_url).strip() or None

        if self.mode == "reply":
            await self.handler.handle_reply_from_interaction(
                interaction,
                reply_content=content,
                attachment_url=attachment_url,
                custom_color=custom_color,
                source_message_id=self.source_message_id,
            )
            return

        await self.handler.handle_confession_interaction(
            interaction,
            content,
            attachment_url=attachment_url,
            custom_color=custom_color,
        )


class PollModal(discord.ui.Modal):
    question = discord.ui.TextInput(
        label="Question",
        style=discord.TextStyle.paragraph,
        max_length=1800,
        required=True,
    )
    options = discord.ui.TextInput(
        label="Opsi (satu per baris)",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
        placeholder="Opsi A\nOpsi B\nOpsi C",
    )
    attachment_url = discord.ui.TextInput(
        label="Link Gambar (opsional)",
        style=discord.TextStyle.short,
        max_length=500,
        required=False,
        placeholder="Paste URL gambar (png/jpg/gif/webp)",
    )
    custom_color = discord.ui.TextInput(
        label="Warna Embed (opsional)",
        style=discord.TextStyle.short,
        max_length=32,
        required=False,
        placeholder="Contoh: ff0000, #ff0000, atau red",
    )

    def __init__(self, handler: "ConfessionHandler"):
        super().__init__(title="Create a Poll")
        self.handler = handler

    async def on_submit(self, interaction: discord.Interaction):
        question = str(self.question).strip()
        options_text = str(self.options).strip()
        custom_color = str(self.custom_color).strip() or None
        attachment_url = str(self.attachment_url).strip() or None

        options = [opt.strip() for opt in options_text.split("\n") if opt.strip()]
        if not options:
            options = ["Yes", "No"]

        await self.handler.handle_poll_interaction(
            interaction,
            question,
            attachment_url=attachment_url,
            custom_color=custom_color,
            options=options,
        )


class ConfessionPanelView(discord.ui.View):
    def __init__(self, handler: "ConfessionHandler"):
        super().__init__(timeout=None)
        self.handler = handler

    @discord.ui.button(label="Submit a confession!", style=discord.ButtonStyle.blurple, custom_id="confess_submit")
    async def submit_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.send_modal(ConfessionModal(self.handler, mode="confess"))

    @discord.ui.button(label="Submit a poll!", style=discord.ButtonStyle.green, custom_id="poll_submit")
    async def poll_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.send_modal(PollModal(self.handler))


class ConfessionItemView(discord.ui.View):
    def __init__(self, handler: "ConfessionHandler"):
        super().__init__(timeout=None)
        self.handler = handler

    @discord.ui.button(label="Submit a confession!", style=discord.ButtonStyle.blurple, custom_id="confess_submit_item")
    async def submit_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.send_modal(ConfessionModal(self.handler, mode="confess"))

    @discord.ui.button(label="Create a poll!", style=discord.ButtonStyle.green, custom_id="poll_submit_item")
    async def poll_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.send_modal(PollModal(self.handler))

    @discord.ui.button(label="Reply", style=discord.ButtonStyle.secondary, custom_id="confess_reply")
    async def reply_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        source_message_id = interaction.message.id if interaction.message else None
        try:
            await interaction.response.send_modal(
                ConfessionModal(self.handler, mode="reply", source_message_id=source_message_id)
            )
        except discord.NotFound:
            return


class PollVoteButton(discord.ui.Button):
    """A single vote button for a poll option. Uses a deterministic custom_id
    so it survives bot restarts (persistent view)."""

    def __init__(self, handler: "ConfessionHandler", message_id: int, option_index: int, label: str):
        custom_id = f"poll_vote_{message_id}_{option_index}"
        super().__init__(label=f"Vote: {label}", style=discord.ButtonStyle.primary, custom_id=custom_id)
        self.handler = handler
        self.poll_message_id = message_id
        self.option_index = option_index

    async def callback(self, interaction: discord.Interaction):
        await self.handler._handle_poll_vote(interaction, self.poll_message_id, self.option_index)


class PollVoteView(discord.ui.View):
    """Persistent view containing vote buttons for a poll."""

    def __init__(self, handler: "ConfessionHandler", message_id: int, options: list[str]):
        super().__init__(timeout=None)
        for idx, opt in enumerate(options):
            self.add_item(PollVoteButton(handler, message_id, idx, opt))


class ReplyNotificationToggleButton(discord.ui.Button):
    def __init__(self, handler: "ConfessionHandler"):
        super().__init__(
            label="Disable reply notifications",
            style=discord.ButtonStyle.danger,
            custom_id="confess_disable_reply_notifications",
        )
        self.handler = handler

    async def callback(self, interaction: discord.Interaction):
        await self.handler.disable_reply_notifications(interaction)


class ReplyNotificationToggleView(discord.ui.View):
    def __init__(self, handler: "ConfessionHandler"):
        super().__init__(timeout=None)
        self.add_item(ReplyNotificationToggleButton(handler))

class ConfessionHandler:
    def __init__(self, bot):
        self.bot = bot
        self._counter = 0
        self._audit_map = {}

        # Per-guild config: guild_id -> {confession_channel_id, audit_channel_id, is_open}
        self._guild_config: dict[int, dict] = {}

        # Seed from env vars for backward-compat (single-server legacy setup)
        _legacy_confession = int(os.getenv("CONFESSION_CHANNEL_ID", "0") or 0)
        _legacy_audit = int(os.getenv("AUDIT_CHANNEL_ID", "0") or 0)
        self._legacy_confession_channel_id = _legacy_confession
        self._legacy_audit_channel_id = _legacy_audit or _legacy_confession

        self._pending_submissions = {}
        # Poll state: message_id -> list[str] (options)
        self._poll_options: dict[int, list[str]] = {}
        # Poll votes: message_id -> dict[user_id -> option_index]
        self._poll_votes: dict[int, dict[int, int]] = {}
        self._reply_notification_disabled_user_ids: set[int] = set()
        self._load_data()

    # ── Guild config helpers ─────────────────────────────────────────

    def _get_guild_config(self, guild_id: int) -> dict:
        if guild_id not in self._guild_config:
            self._guild_config[guild_id] = {
                "confession_channel_id": 0,
                "audit_channel_id": 0,
                "is_open": True,
            }
        return self._guild_config[guild_id]

    def get_confession_channel_id(self, guild_id: int) -> int:
        return self._get_guild_config(guild_id).get("confession_channel_id", 0)

    def get_audit_channel_id(self, guild_id: int) -> int:
        return self._get_guild_config(guild_id).get("audit_channel_id", 0)

    def is_guild_open(self, guild_id: int) -> bool:
        return self._get_guild_config(guild_id).get("is_open", True)

    def set_guild_open(self, guild_id: int, value: bool):
        self._get_guild_config(guild_id)["is_open"] = value
        self._save_data()

    def set_guild_channels(self, guild_id: int, confession_channel_id: int, audit_channel_id: int):
        cfg = self._get_guild_config(guild_id)
        cfg["confession_channel_id"] = confession_channel_id
        cfg["audit_channel_id"] = audit_channel_id
        self._save_data()

    def _try_legacy_assign(self, guild_id: int):
        """Auto-assign env-var channels to this guild if no config exists yet."""
        if not self._legacy_confession_channel_id:
            return
        cfg = self._get_guild_config(guild_id)
        if not cfg["confession_channel_id"]:
            cfg["confession_channel_id"] = self._legacy_confession_channel_id
            cfg["audit_channel_id"] = self._legacy_audit_channel_id
            self._legacy_confession_channel_id = 0
            self._legacy_audit_channel_id = 0
            self._save_data()

    # ── Persistence ──────────────────────────────────────────────────

    def _load_data(self):
        filepath = "bot_data.json"
        if not os.path.exists(filepath):
            filepath = "polls.json"
            if not os.path.exists(filepath):
                return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_options = data.get("options", {})
            self._poll_options = {int(k): v for k, v in raw_options.items()}

            raw_votes = data.get("votes", {})
            self._poll_votes = {
                int(msg_id): {int(user_id): opt_idx for user_id, opt_idx in user_vote.items()}
                for msg_id, user_vote in raw_votes.items()
            }

            self._counter = data.get("counter", self._counter)
            raw_audit = data.get("audit_map", {})
            self._audit_map = {int(k): v for k, v in raw_audit.items()}

            raw_reply_opt_outs = data.get("reply_notification_disabled_user_ids", [])
            self._reply_notification_disabled_user_ids = {int(user_id) for user_id in raw_reply_opt_outs}

            raw_guilds = data.get("guild_config", {})
            for gid, cfg in raw_guilds.items():
                self._guild_config[int(gid)] = cfg
        except Exception as e:
            print(f"Error loading data: {e}")

    def _save_data(self):
        filepath = "bot_data.json"
        try:
            data = {
                "options": {str(k): v for k, v in self._poll_options.items()},
                "votes": {
                    str(msg_id): {str(user_id): opt_idx for user_id, opt_idx in user_vote.items()}
                    for msg_id, user_vote in self._poll_votes.items()
                },
                "counter": self._counter,
                "audit_map": {str(k): v for k, v in self._audit_map.items()},
                "reply_notification_disabled_user_ids": sorted(self._reply_notification_disabled_user_ids),
                "guild_config": {str(gid): cfg for gid, cfg in self._guild_config.items()},
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving data: {e}")

    def get_persistent_view(self) -> discord.ui.View:
        return ConfessionPanelView(self)

    def get_persistent_reply_view(self) -> discord.ui.View:
        return ConfessionItemView(self)

    def get_persistent_reply_notification_view(self) -> discord.ui.View:
        return ReplyNotificationToggleView(self)

    def is_reply_notification_disabled(self, user_id: int) -> bool:
        return user_id in self._reply_notification_disabled_user_ids

    async def disable_reply_notifications(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if self.is_reply_notification_disabled(user_id):
            if not interaction.response.is_done():
                await interaction.response.defer()
            try:
                await interaction.followup.send("Reply notifications sudah dimatikan.")
            except Exception:
                pass
            return

        if not interaction.response.is_done():
            await interaction.response.defer()

        self._reply_notification_disabled_user_ids.add(user_id)
        self._save_data()

        try:
            if interaction.message is not None:
                await interaction.message.edit(view=None)
        except discord.HTTPException:
            pass

        try:
            await interaction.followup.send("Reply notifications sudah dimatikan.")
        except Exception:
            pass

    def _next_id(self) -> int:
        self._counter += 1
        return self._counter

    def _extract_confession_id(self, message: discord.Message) -> Optional[int]:
        if not message.embeds:
            return None

        title = message.embeds[0].title or ""
        m = CONFESSION_ID_RE.search(title)
        if not m:
            return None
        return int(m.group(1))

    def _build_embed(self, title: str, content: str, color: discord.Color, attachment_url: Optional[str]):
        embed = discord.Embed(title=title, description=content, color=color)
        embed.set_footer(text="Anonim • Rahasia tinggi")
        if attachment_url:
            lower_attachment = attachment_url.lower().split("?", 1)[0]
            if lower_attachment.endswith(ALLOWED_IMAGE_EXTENSIONS):
                embed.set_image(url=attachment_url)
            else:
                embed.add_field(name="Attachment", value=attachment_url, inline=False)
        return embed

    def _resolve_attachment_url(
        self,
        attachment: Optional[discord.Attachment],
        attachment_url: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        if attachment is not None:
            if attachment.size > MAX_ATTACHMENT_SIZE_BYTES:
                return None, "Ukuran file terlalu besar. Maksimal 500MB."

            content_type = (attachment.content_type or "").lower()
            filename = (attachment.filename or "").lower()
            is_image = content_type.startswith("image/") or filename.endswith(ALLOWED_IMAGE_EXTENSIONS)
            if not is_image:
                return None, "Hanya file gambar yang didukung (png/jpg/jpeg/gif/webp)."

            return attachment.url, None

        return attachment_url, None

    def _resolve_custom_color(
        self,
        custom_color: Optional[str],
        fallback_color: discord.Color,
    ) -> Optional[discord.Color]:
        if not custom_color:
            return fallback_color

        normalized = custom_color.strip().lower()
        if not normalized:
            return fallback_color

        named_colors = {
            "red": discord.Color.red(),
            "blue": discord.Color.blue(),
            "green": discord.Color.green(),
            "yellow": discord.Color.yellow(),
            "orange": discord.Color.orange(),
            "teal": discord.Color.teal(),
            "purple": discord.Color.purple(),
            "blurple": discord.Color.blurple(),
            "gold": discord.Color.gold(),
            "dark blue": discord.Color.dark_blue(),
            "dark green": discord.Color.dark_green(),
            "dark purple": discord.Color.dark_purple(),
        }
        if normalized in named_colors:
            return named_colors[normalized]

        hex_value = normalized.lstrip("#")
        if len(hex_value) == 3 and all(char in "0123456789abcdef" for char in hex_value):
            hex_value = "".join(char * 2 for char in hex_value)
        if len(hex_value) == 6 and all(char in "0123456789abcdef" for char in hex_value):
            return discord.Color(int(hex_value, 16))

        return None

    async def _respond_interaction(self, interaction: discord.Interaction, content: str):
        try:
            if interaction.response.is_done():
                await interaction.followup.send(content, ephemeral=True)
            else:
                await interaction.response.send_message(content, ephemeral=True)
        except discord.NotFound:
            return

    async def handle_pending_submission_message(self, message: discord.Message) -> bool:
        return False

    async def _notify_original_author(
        self,
        guild: discord.Guild,
        source_message: discord.Message,
        origin_confession_id: int,
        reply_message: discord.Message,
    ):
        original_user_id = self._audit_map.get(origin_confession_id)
        if not original_user_id:
            return

        if self.is_reply_notification_disabled(original_user_id):
            return

        member = guild.get_member(original_user_id)
        if member is None:
            try:
                member = await guild.fetch_member(original_user_id)
            except discord.HTTPException:
                return

        try:
            await member.send(
                f"Ada balasan baru pada confession anonim kamu (#{origin_confession_id}).\n"
                f"Link thread: {reply_message.jump_url}\n"
                "Ini hanya notifikasi, identitas pengirim balasan tetap rahasia.\n"
                "Jika tidak ingin menerima notifikasi seperti ini lagi, klik tombol di bawah.",
                view=ReplyNotificationToggleView(self),
            )
        except (discord.Forbidden, discord.HTTPException):
            return

    async def _send_audit_log(
        self,
        guild: discord.Guild,
        author: discord.Member,
        confession_id: int,
        content: str,
        public_message: discord.Message,
        kind: str,
        extra_link_text: Optional[str] = None,
    ):
        audit_channel_id = self.get_audit_channel_id(guild.id)
        if not audit_channel_id:
            return

        audit_channel = guild.get_channel(audit_channel_id)
        if not audit_channel:
            return

        audit_embed = discord.Embed(
            title=f"{kind} (#{confession_id})",
            description=content,
            color=discord.Color.orange() if kind == "Anonymous Confession" else discord.Color.teal(),
        )
        audit_embed.add_field(name="User", value=f"{author} ({author.id})", inline=False)
        audit_embed.add_field(name="ID", value=str(author.id), inline=False)
        audit_embed.add_field(name="Link", value=public_message.jump_url, inline=False)
        if extra_link_text:
            audit_embed.add_field(name="Original", value=extra_link_text, inline=False)
        await audit_channel.send(embed=audit_embed)

    async def _post_confession(
        self,
        guild: discord.Guild,
        author: discord.Member,
        content: str,
        attachment_url: Optional[str] = None,
        custom_color: Optional[str] = None,
    ) -> Optional[discord.Message]:
        self._try_legacy_assign(guild.id)
        confession_channel_id = self.get_confession_channel_id(guild.id)
        if not confession_channel_id:
            return None

        confession_channel = guild.get_channel(confession_channel_id)
        if confession_channel is None:
            return None

        confession_id = self._next_id()
        embed_color = self._resolve_custom_color(custom_color, discord.Color.blurple())
        if embed_color is None:
            raise ValueError("Invalid custom color")
        embed = self._build_embed(
            f"Anonymous Confession (#{confession_id})",
            content,
            embed_color,
            attachment_url,
        )

        sent_msg = await confession_channel.send(embed=embed, view=ConfessionItemView(self))
        self._audit_map[confession_id] = author.id
        self._save_data()

        await self._send_audit_log(
            guild,
            author,
            confession_id,
            content,
            sent_msg,
            kind="Anonymous Confession",
        )
        return sent_msg

    async def _post_reply(
        self,
        guild: discord.Guild,
        author: discord.Member,
        source_message: discord.Message,
        content: str,
        attachment_url: Optional[str] = None,
        custom_color: Optional[str] = None,
        attachment: Optional[discord.Attachment] = None,
    ) -> Optional[discord.Message]:
        origin_confession_id = self._extract_confession_id(source_message)
        if origin_confession_id is None:
            return None

        resolved_attachment_url, attachment_error = self._resolve_attachment_url(attachment, attachment_url)
        if attachment_error:
            raise ValueError(attachment_error)

        thread_name = f"Confession Replies (#{origin_confession_id})"
        thread = source_message.thread
        if thread is None:
            thread = await source_message.create_thread(name=thread_name, auto_archive_duration=1440)

        reply_id = self._next_id()
        embed_color = self._resolve_custom_color(custom_color, discord.Color.teal())
        if embed_color is None:
            raise ValueError("Invalid custom color")
        embed = self._build_embed(
            f"Anonymous Reply (#{reply_id})",
            f"**Pesan:**\n\"{content}\"",
            embed_color,
            resolved_attachment_url,
        )
        sent_msg = await thread.send(embed=embed)
        self._audit_map[reply_id] = author.id
        self._save_data()

        await self._send_audit_log(
            guild,
            author,
            reply_id,
            content,
            sent_msg,
            kind="Anonymous Reply",
            extra_link_text=source_message.jump_url,
        )

        await self._notify_original_author(guild, source_message, origin_confession_id, sent_msg)
        return sent_msg

    async def setup_channels(self, ctx, confession_channel: discord.TextChannel, audit_channel: discord.TextChannel):
        self.set_guild_channels(ctx.guild.id, confession_channel.id, audit_channel.id)
        await ctx.send(
            f"Setup selesai. Channel confession: {confession_channel.mention}, audit: {audit_channel.mention}"
        )

    async def post_panel(self, ctx):
        self._try_legacy_assign(ctx.guild.id)
        confession_channel_id = self.get_confession_channel_id(ctx.guild.id)
        if not confession_channel_id:
            await ctx.send("Set channel dulu pakai !confess_setup #confession #audit")
            return

        confession_channel = ctx.guild.get_channel(confession_channel_id)
        if confession_channel is None:
            await ctx.send("Confession channel tidak ditemukan. Jalankan setup ulang.")
            return

        panel = discord.Embed(
            title="Confessions",
            description="Kirim confession anonim lewat tombol di bawah. Jangan bagikan data sensitif.",
            color=discord.Color.dark_blue(),
        )
        await confession_channel.send(embed=panel, view=ConfessionPanelView(self))
        await ctx.send("Panel confession berhasil dipasang.", delete_after=8)

    async def handle_confession(
        self,
        ctx,
        confession_message,
        custom_color: Optional[str] = None,
        attachment: Optional[discord.Attachment] = None,
        attachment_url: Optional[str] = None,
    ):
        guild_id = ctx.guild.id
        self._try_legacy_assign(guild_id)

        if not self.is_guild_open(guild_id):
            await ctx.send("Confession sedang ditutup.")
            return

        if not self.get_confession_channel_id(guild_id):
            await ctx.send("Channel confession belum diset. Jalankan !confess_setup dulu.")
            return

        resolved_attachment_url, attachment_error = self._resolve_attachment_url(attachment, attachment_url)
        if attachment_error:
            await ctx.send(attachment_error)
            return

        try:
            sent_msg = await self._post_confession(
                ctx.guild,
                ctx.author,
                confession_message,
                attachment_url=resolved_attachment_url,
                custom_color=custom_color,
            )
        except ValueError:
            await ctx.send("Custom color tidak valid. Gunakan hex seperti #ff0000 atau nama warna seperti red.")
            return
        if sent_msg is None:
            await ctx.send("Confession channel tidak ditemukan. Cek setup channel.")
            return

        try:
            await ctx.message.delete()
        except Exception:
            pass

        await ctx.send("Pesan confession sudah dikirim. Ini anonim dan rahasia.", delete_after=8)

    async def close_confession(self, ctx):
        self.set_guild_open(ctx.guild.id, False)
        await ctx.send("Confession submission ditutup.")

    async def open_confession(self, ctx):
        self.set_guild_open(ctx.guild.id, True)
        await ctx.send("Confession submission dibuka.")

    async def handle_confession_interaction(
        self,
        interaction: discord.Interaction,
        confession_message: str,
        attachment_url: Optional[str],
        custom_color: Optional[str] = None,
        attachment: Optional[discord.Attachment] = None,
    ):
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.NotFound:
                return

        if not interaction.guild:
            await self._respond_interaction(interaction, "Confession hanya bisa di server.")
            return

        guild_id = interaction.guild.id
        self._try_legacy_assign(guild_id)

        if not self.is_guild_open(guild_id):
            await self._respond_interaction(interaction, "Confession sedang ditutup.")
            return

        resolved_attachment_url, attachment_error = self._resolve_attachment_url(attachment, attachment_url)
        if attachment_error:
            await self._respond_interaction(interaction, attachment_error)
            return

        try:
            sent_msg = await self._post_confession(
                interaction.guild,
                interaction.user,
                confession_message,
                resolved_attachment_url,
                custom_color,
            )
        except ValueError:
            await self._respond_interaction(
                interaction,
                "Custom color tidak valid. Gunakan hex seperti #ff0000 atau nama warna seperti red.",
            )
            return
        if sent_msg is None:
            await self._respond_interaction(interaction, "Confession channel belum siap. Jalankan !confess_setup dulu.")
            return

        await self._respond_interaction(interaction, "Confession sudah dikirim. Ini bersifat anonim dan rahasia tinggi.")

    async def handle_reply_from_interaction(
        self,
        interaction: discord.Interaction,
        reply_content: str,
        attachment_url: Optional[str] = None,
        custom_color: Optional[str] = None,
        source_message_id: Optional[int] = None,
        attachment: Optional[discord.Attachment] = None,
    ):
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.NotFound:
                return

        if not interaction.guild:
            await self._respond_interaction(interaction, "Reply hanya bisa di server.")
            return

        guild_id = interaction.guild.id
        self._try_legacy_assign(guild_id)
        confession_channel_id = self.get_confession_channel_id(guild_id)

        if not source_message_id or not confession_channel_id:
            await self._respond_interaction(interaction, "Pesan confession sumber tidak valid.")
            return

        confession_channel = interaction.guild.get_channel(confession_channel_id)
        if confession_channel is None:
            await self._respond_interaction(interaction, "Confession channel tidak ditemukan.")
            return

        source_message = await confession_channel.fetch_message(source_message_id)
        try:
            sent_msg = await self._post_reply(
                interaction.guild,
                interaction.user,
                source_message,
                reply_content,
                attachment_url,
                custom_color,
                attachment,
            )
        except ValueError as e:
            err_msg = str(e)
            if "color" in err_msg.lower():
                err_msg = "Custom color tidak valid. Gunakan hex seperti #ff0000 atau nama warna seperti red."
            await self._respond_interaction(interaction, err_msg)
            return
        if sent_msg is None:
            await self._respond_interaction(interaction, "Tombol reply harus dipakai di pesan confession bot.")
            return

        await self._respond_interaction(interaction, "Reply anonim sudah dikirim ke thread confession.")

    async def _post_poll(
        self,
        guild: discord.Guild,
        author: discord.Member,
        question: str,
        attachment_url: Optional[str] = None,
        custom_color: Optional[str] = None,
        options: Optional[list[str]] = None,
    ) -> Optional[discord.Message]:
        self._try_legacy_assign(guild.id)
        confession_channel_id = self.get_confession_channel_id(guild.id)
        if not confession_channel_id:
            return None

        confession_channel = guild.get_channel(confession_channel_id)
        if confession_channel is None:
            return None

        poll_id = self._next_id()
        embed_color = self._resolve_custom_color(custom_color, discord.Color.green())
        if embed_color is None:
            raise ValueError("Invalid custom color")

        # Build embed with question and option fields
        if options is None:
            options = ["Yes", "No"]
        
        embed = self._build_embed(
            f"Anonymous Poll (#{poll_id})",
            question,
            embed_color,
            attachment_url,
        )
        
        # Add each option as a field with formatted vote display + progress bar
        for idx, opt in enumerate(options):
            bar = self._progress_bar(0)
            embed.add_field(name=f"📊 {opt}", value=f"{bar}  **0** votes", inline=False)
        embed.set_footer(text="Total: 0 votes • Anonim")
        
        sent_msg = await confession_channel.send(embed=embed)
        # store poll state
        self._poll_options[sent_msg.id] = options
        self._poll_votes[sent_msg.id] = {}
        self._audit_map[poll_id] = author.id
        self._save_data()
        
        # attach interactive vote buttons
        view = self._make_poll_view(sent_msg.id, options)
        try:
            await sent_msg.edit(view=view)
        except Exception:
            pass

        await self._send_audit_log(
            guild,
            author,
            poll_id,
            question,
            sent_msg,
            kind="Anonymous Poll",
        )
        return sent_msg

    def _make_poll_view(self, message_id: int, options: list[str]) -> discord.ui.View:
        """Create a PollVoteView (persistent) for the given poll."""
        return PollVoteView(self, message_id, options)

    def get_all_persistent_poll_views(self) -> list[discord.ui.View]:
        """Return persistent views for every stored poll so they can be
        registered in on_ready and survive bot restarts."""
        views: list[discord.ui.View] = []
        for message_id, options in self._poll_options.items():
            views.append(PollVoteView(self, message_id, options))
        return views

    @staticmethod
    def _progress_bar(percentage: float, length: int = 10) -> str:
        filled = round(percentage / 100 * length)
        return "█" * filled + "░" * (length - filled)

    async def _handle_poll_vote(self, interaction: discord.Interaction, message_id: int, option_index: int):
        # ensure poll exists
        options = self._poll_options.get(message_id)
        if not options:
            # Reconstruct options from the embed fields as a fallback
            try:
                poll_msg = interaction.message or await interaction.channel.fetch_message(message_id)
                if poll_msg and poll_msg.embeds:
                    embed = poll_msg.embeds[0]
                    reconstructed = []
                    for field in embed.fields:
                        if field.name.startswith("📊 "):
                            reconstructed.append(field.name[2:])
                    if reconstructed:
                        self._poll_options[message_id] = reconstructed
                        options = reconstructed
            except Exception:
                pass

        if not options:
            try:
                await interaction.response.send_message("Poll tidak ditemukan.", ephemeral=True)
            except Exception:
                pass
            return

        user_id = interaction.user.id
        user_votes = self._poll_votes.setdefault(message_id, {})
        previous = user_votes.get(user_id)
        if previous is not None and previous == option_index:
            try:
                await interaction.response.send_message("Kamu sudah memilih opsi ini.", ephemeral=True)
            except Exception:
                pass
            return

        user_votes[user_id] = option_index
        self._save_polls()

        # recompute counts
        counts = [0] * len(options)
        for v in user_votes.values():
            if 0 <= v < len(options):
                counts[v] += 1

        # update embed
        poll_msg = interaction.message
        if not poll_msg:
            try:
                channel = interaction.channel
                poll_msg = await channel.fetch_message(message_id)
            except Exception:
                poll_msg = None

        if poll_msg and poll_msg.embeds:
            embed = poll_msg.embeds[0]
            total_votes = sum(counts)
            # Rebuild option fields with progress bar
            embed.clear_fields()
            for i, opt in enumerate(options):
                vote_count = counts[i] if i < len(counts) else 0
                percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
                bar = self._progress_bar(percentage)
                value_text = f"{bar}  **{vote_count}** vote{'s' if vote_count != 1 else ''}"
                if total_votes > 0:
                    value_text += f" ({percentage:.0f}%)"
                embed.add_field(name=f"📊 {opt}", value=value_text, inline=False)
            embed.set_footer(text=f"Total: {total_votes} vote{'s' if total_votes != 1 else ''} • Anonim")
            try:
                await poll_msg.edit(embed=embed)
            except Exception:
                pass

        try:
            await interaction.response.send_message("Pilihan kamu berhasil dicatat.", ephemeral=True)
        except Exception:
            return

    async def handle_poll_vote_from_interaction(self, interaction: discord.Interaction, message_id: int, option_index: int):
        await self._handle_poll_vote(interaction, message_id, option_index)

    async def handle_poll(
        self,
        ctx,
        question: str,
        custom_color: Optional[str] = None,
        attachment: Optional[discord.Attachment] = None,
        attachment_url: Optional[str] = None,
        options: Optional[list[str]] = None,
    ):
        guild_id = ctx.guild.id
        self._try_legacy_assign(guild_id)

        if not self.is_guild_open(guild_id):
            await ctx.send("Poll sedang ditutup.")
            return

        if not self.get_confession_channel_id(guild_id):
            await ctx.send("Channel confession belum diset. Jalankan !confess_setup dulu.")
            return

        resolved_attachment_url, attachment_error = self._resolve_attachment_url(attachment, attachment_url)
        if attachment_error:
            await ctx.send(attachment_error)
            return

        try:
            sent_msg = await self._post_poll(
                ctx.guild,
                ctx.author,
                question,
                attachment_url=resolved_attachment_url,
                custom_color=custom_color,
                options=options,
            )
        except ValueError:
            await ctx.send("Custom color tidak valid. Gunakan hex seperti #ff0000 atau nama warna seperti red.")
            return
        if sent_msg is None:
            await ctx.send("Confession channel tidak ditemukan. Cek setup channel.")
            return

        await ctx.send("Poll sudah dikirim. Ini anonim dan rahasia.", delete_after=8)

    async def handle_poll_interaction(
        self,
        interaction: discord.Interaction,
        question: str,
        attachment_url: Optional[str],
        custom_color: Optional[str] = None,
        attachment: Optional[discord.Attachment] = None,
        options: Optional[list[str]] = None,
    ):
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.NotFound:
                return

        if not interaction.guild:
            await self._respond_interaction(interaction, "Poll hanya bisa di server.")
            return

        guild_id = interaction.guild.id
        self._try_legacy_assign(guild_id)

        if not self.is_guild_open(guild_id):
            await self._respond_interaction(interaction, "Poll sedang ditutup.")
            return

        resolved_attachment_url, attachment_error = self._resolve_attachment_url(attachment, attachment_url)
        if attachment_error:
            await self._respond_interaction(interaction, attachment_error)
            return

        try:
            sent_msg = await self._post_poll(
                interaction.guild,
                interaction.user,
                question,
                resolved_attachment_url,
                custom_color,
                options,
            )
        except ValueError:
            await self._respond_interaction(
                interaction,
                "Custom color tidak valid. Gunakan hex seperti #ff0000 atau nama warna seperti red.",
            )
            return
        if sent_msg is None:
            await self._respond_interaction(interaction, "Confession channel belum siap. Jalankan !confess_setup dulu.")
            return

        await self._respond_interaction(interaction, "Poll sudah dikirim. Ini bersifat anonim dan rahasia tinggi.")

    async def handle_reply_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        self._try_legacy_assign(guild_id)

        if not self.is_guild_open(guild_id):
            return

        if message.reference is None or message.reference.message_id is None:
            return

        confession_channel_id = self.get_confession_channel_id(guild_id)
        if not confession_channel_id or message.channel.id != confession_channel_id:
            return

        source_message = None
        if isinstance(message.reference.resolved, discord.Message):
            source_message = message.reference.resolved
        else:
            source_message = await message.channel.fetch_message(message.reference.message_id)

        if source_message.author.id != self.bot.user.id:
            return

        sent_msg = await self._post_reply(message.guild, message.author, source_message, message.content)
        if sent_msg is None:
            return

        try:
            await message.delete()
        except Exception:
            pass

        notice = await message.channel.send(
            f"{message.author.mention} reply anonim sudah dipindahkan ke thread.",
            delete_after=6,
        )
        return notice

    async def reveal_confession_author(self, ctx, confession_id: int):
        user_id = self._audit_map.get(confession_id)
        if not user_id:
            await ctx.send("Confession ID tidak ditemukan.")
            return

        member = ctx.guild.get_member(user_id)
        who = f"{member.mention} (`{user_id}`)" if member else f"`{user_id}`"
        await ctx.send(f"Confession #{confession_id} dikirim oleh {who}")