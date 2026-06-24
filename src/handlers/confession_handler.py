import os
import re
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
        label="Attachment URL (optional)",
        style=discord.TextStyle.short,
        max_length=400,
        required=False,
    )
    custom_color = discord.ui.TextInput(
        label="Custom Color (optional)",
        style=discord.TextStyle.short,
        max_length=32,
        required=False,
        placeholder="Ex: ff0000, #ff0000, or red",
    )

    def __init__(self, handler: "ConfessionHandler", mode: str, source_message_id: Optional[int] = None):
        super().__init__(title="Submit a Confession")
        self.handler = handler
        self.mode = mode
        self.source_message_id = source_message_id

    async def on_submit(self, interaction: discord.Interaction):
        content = str(self.confession_content).strip()
        attachment = str(self.attachment_url).strip() or None
        custom_color = str(self.custom_color).strip() or None

        if self.mode == "reply":
            await self.handler.handle_reply_from_interaction(
                interaction,
                content,
                attachment,
                custom_color,
                self.source_message_id,
            )
            return

        await self.handler.handle_confession_interaction(interaction, content, attachment, custom_color)


class PollModal(discord.ui.Modal):
    question = discord.ui.TextInput(
        label="Question",
        style=discord.TextStyle.paragraph,
        max_length=1800,
        required=True,
    )
    attachment_url = discord.ui.TextInput(
        label="Attachment (optional)",
        style=discord.TextStyle.short,
        max_length=400,
        required=False,
    )
    custom_color = discord.ui.TextInput(
        label="Custom Color (optional)",
        style=discord.TextStyle.short,
        max_length=32,
        required=False,
        placeholder="Ex: ff0000, #ff0000, or red",
    )

    def __init__(self, handler: "ConfessionHandler"):
        super().__init__(title="Create a Poll")
        self.handler = handler

    async def on_submit(self, interaction: discord.Interaction):
        question = str(self.question).strip()
        attachment = str(self.attachment_url).strip() or None
        custom_color = str(self.custom_color).strip() or None
        await self.handler.handle_poll_interaction(interaction, question, attachment, custom_color)


class ConfessionPanelView(discord.ui.View):
    def __init__(self, handler: "ConfessionHandler"):
        super().__init__(timeout=None)
        self.handler = handler

    @discord.ui.button(label="Submit a confession!", style=discord.ButtonStyle.blurple, custom_id="confess_submit")
    async def submit_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            await interaction.response.send_modal(ConfessionModal(self.handler, mode="confess"))
        except discord.NotFound:
            return

    @discord.ui.button(label="Submit a poll!", style=discord.ButtonStyle.green, custom_id="poll_submit")
    async def poll_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            await interaction.response.send_modal(PollModal(self.handler))
        except discord.NotFound:
            return


class ConfessionItemView(discord.ui.View):
    def __init__(self, handler: "ConfessionHandler"):
        super().__init__(timeout=None)
        self.handler = handler

    @discord.ui.button(label="Submit a confession!", style=discord.ButtonStyle.blurple, custom_id="confess_submit_item")
    async def submit_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            await interaction.response.send_modal(ConfessionModal(self.handler, mode="confess"))
        except discord.NotFound:
            return

    @discord.ui.button(label="Create a poll!", style=discord.ButtonStyle.green, custom_id="poll_submit_item")
    async def poll_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            await interaction.response.send_modal(PollModal(self.handler))
        except discord.NotFound:
            return

    @discord.ui.button(label="Reply", style=discord.ButtonStyle.secondary, custom_id="confess_reply")
    async def reply_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        source_message_id = interaction.message.id if interaction.message else None
        try:
            await interaction.response.send_modal(
                ConfessionModal(self.handler, mode="reply", source_message_id=source_message_id)
            )
        except discord.NotFound:
            return

class ConfessionHandler:
    def __init__(self, bot):
        self.bot = bot
        self.is_open = True
        self._counter = 0
        self._audit_map = {}

        self.bot.confession_channel_id = int(os.getenv("CONFESSION_CHANNEL_ID", "0") or 0)
        self.bot.audit_channel_id = int(os.getenv("AUDIT_CHANNEL_ID", "0") or 0)

    def get_persistent_view(self) -> discord.ui.View:
        return ConfessionPanelView(self)

    def get_persistent_reply_view(self) -> discord.ui.View:
        return ConfessionItemView(self)

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
                "Ini hanya notifikasi, identitas pengirim balasan tetap rahasia."
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
        audit_channel_id = getattr(self.bot, "audit_channel_id", None)
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
        confession_channel_id = getattr(self.bot, "confession_channel_id", None)
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
    ) -> Optional[discord.Message]:
        origin_confession_id = self._extract_confession_id(source_message)
        if origin_confession_id is None:
            return None

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
            content,
            embed_color,
            attachment_url,
        )
        sent_msg = await thread.send(embed=embed)
        self._audit_map[reply_id] = author.id

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
        self.bot.confession_channel_id = confession_channel.id
        self.bot.audit_channel_id = audit_channel.id
        await ctx.send(
            f"Setup selesai. Channel confession: {confession_channel.mention}, audit: {audit_channel.mention}"
        )

    async def post_panel(self, ctx):
        confession_channel_id = getattr(self.bot, "confession_channel_id", None)
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

    async def handle_confession(self, ctx, confession_message, custom_color: Optional[str] = None):
        if not self.is_open:
            await ctx.send("Confession sedang ditutup.")
            return

        if not getattr(self.bot, "confession_channel_id", None):
            await ctx.send("Channel confession belum diset. Jalankan !confess_setup dulu.")
            return

        try:
            sent_msg = await self._post_confession(ctx.guild, ctx.author, confession_message, custom_color=custom_color)
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
        self.is_open = False
        await ctx.send("Confession submission ditutup.")

    async def open_confession(self, ctx):
        self.is_open = True
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

        if not self.is_open:
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
        attachment_url: Optional[str],
        custom_color: Optional[str],
        source_message_id: Optional[int],
    ):
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.NotFound:
                return

        if not interaction.guild:
            await self._respond_interaction(interaction, "Reply hanya bisa di server.")
            return

        if not source_message_id or not getattr(self.bot, "confession_channel_id", None):
            await self._respond_interaction(interaction, "Pesan confession sumber tidak valid.")
            return

        confession_channel = interaction.guild.get_channel(self.bot.confession_channel_id)
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
            )
        except ValueError:
            await self._respond_interaction(
                interaction,
                "Custom color tidak valid. Gunakan hex seperti #ff0000 atau nama warna seperti red.",
            )
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
    ) -> Optional[discord.Message]:
        confession_channel_id = getattr(self.bot, "confession_channel_id", None)
        if not confession_channel_id:
            return None

        confession_channel = guild.get_channel(confession_channel_id)
        if confession_channel is None:
            return None

        poll_id = self._next_id()
        embed_color = self._resolve_custom_color(custom_color, discord.Color.green())
        if embed_color is None:
            raise ValueError("Invalid custom color")

        embed = self._build_embed(
            f"Anonymous Poll (#{poll_id})",
            question,
            embed_color,
            attachment_url,
        )
        sent_msg = await confession_channel.send(embed=embed, view=ConfessionItemView(self))
        self._audit_map[poll_id] = author.id

        await self._send_audit_log(
            guild,
            author,
            poll_id,
            question,
            sent_msg,
            kind="Anonymous Poll",
        )
        return sent_msg

    async def handle_poll(self, ctx, question: str, custom_color: Optional[str] = None):
        if not self.is_open:
            await ctx.send("Poll sedang ditutup.")
            return

        if not getattr(self.bot, "confession_channel_id", None):
            await ctx.send("Channel confession belum diset. Jalankan !confess_setup dulu.")
            return

        try:
            sent_msg = await self._post_poll(ctx.guild, ctx.author, question, custom_color=custom_color)
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
    ):
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.NotFound:
                return

        if not interaction.guild:
            await self._respond_interaction(interaction, "Poll hanya bisa di server.")
            return

        if not self.is_open:
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

        if not self.is_open:
            return

        if message.reference is None or message.reference.message_id is None:
            return

        confession_channel_id = getattr(self.bot, "confession_channel_id", None)
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