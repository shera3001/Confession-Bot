import discord
from discord import app_commands
from discord.ext import commands
import os
from typing import Optional
from dotenv import load_dotenv
from src.handlers.confession_handler import ConfessionHandler

load_dotenv()

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
handler = ConfessionHandler(bot)
_persistent_view_added = False
_tree_synced = False


async def ensure_mod(ctx):
    if ctx.author.guild_permissions.manage_messages or ctx.author.guild_permissions.administrator:
        return True
    await ctx.send("Hanya moderator/admin yang bisa pakai command ini.")
    return False


async def ensure_mod_interaction(interaction: discord.Interaction):
    perms = interaction.user.guild_permissions
    if perms.manage_messages or perms.administrator:
        return True
    if interaction.response.is_done():
        await interaction.followup.send("Hanya moderator/admin yang bisa pakai command ini.", ephemeral=True)
    else:
        await interaction.response.send_message("Hanya moderator/admin yang bisa pakai command ini.", ephemeral=True)
    return False

@bot.event
async def on_ready():
    global _persistent_view_added, _tree_synced
    if not _persistent_view_added:
        bot.add_view(handler.get_persistent_view())
        bot.add_view(handler.get_persistent_reply_view())
        # Register all stored poll vote views so buttons survive restarts
        for poll_view in handler.get_all_persistent_poll_views():
            bot.add_view(poll_view)
        _persistent_view_added = True
    if not _tree_synced:
        await bot.tree.sync()
        _tree_synced = True
    print(f'Logged in as {bot.user.name} - {bot.user.id}')


@bot.event
async def on_message(message):
    await handler.handle_reply_message(message)
    await bot.process_commands(message)

@bot.command(name='confess')
async def confess(ctx, *, confession: str):
    first_attachment = ctx.message.attachments[0] if ctx.message.attachments else None
    await handler.handle_confession(ctx, confession, attachment=first_attachment)


@bot.command(name='poll')
async def poll(ctx, *, question: str):
    first_attachment = ctx.message.attachments[0] if ctx.message.attachments else None
    
    parsed_options = None
    if "|" in question:
        parts = question.split("|")
        question_text = parts[0].strip()
        parsed_options = [opt.strip() for opt in parts[1:] if opt.strip()]
    else:
        question_text = question.strip()
        
    await handler.handle_poll(
        ctx,
        question_text,
        attachment=first_attachment,
        options=parsed_options,
    )


@bot.command(name='confess_setup')
async def confess_setup(
    ctx,
    confession_channel: discord.TextChannel,
    audit_channel: Optional[discord.TextChannel] = None,
):
    if not await ensure_mod(ctx):
        return
    if audit_channel is None:
        audit_channel = confession_channel
    await handler.setup_channels(ctx, confession_channel, audit_channel)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        if ctx.command and ctx.command.name == "confess_setup":
            await ctx.send(
                "Format setup: `!confess_setup #confessions #log-audit-confess`\n"
                "Kalau 1 channel saja: `!confess_setup #confessions`"
            )
            return
    if isinstance(error, commands.ChannelNotFound):
        await ctx.send(
            "Channel tidak ditemukan. Pakai mention channel dari autocomplete Discord.\n"
            "Contoh: `!confess_setup #confessions #log-audit-confess`\n"
            "Alternatif lebih aman: pakai slash command `/confess_setup`."
        )
        return
    raise error


@bot.command(name='confess_panel')
async def confess_panel(ctx):
    if not await ensure_mod(ctx):
        return
    await handler.post_panel(ctx)


@bot.command(name='confess_close')
async def confess_close(ctx):
    if not await ensure_mod(ctx):
        return
    await handler.close_confession(ctx)


@bot.command(name='confess_open')
async def confess_open(ctx):
    if not await ensure_mod(ctx):
        return
    await handler.open_confession(ctx)


@bot.command(name='confess_audit')
async def confess_audit(ctx, confession_id: int):
    if not await ensure_mod(ctx):
        return
    await handler.reveal_confession_author(ctx, confession_id)


@bot.tree.command(name="confess", description="Kirim confession anonim")
@app_commands.describe(
    confession="Isi confession",
    attachment="File attachment opsional",
    attachment_url="URL attachment opsional",
    custom_color="Warna kustom opsional",
)
async def slash_confess(
    interaction: discord.Interaction,
    confession: str,
    attachment: Optional[discord.Attachment] = None,
    attachment_url: Optional[str] = None,
    custom_color: Optional[str] = None,
):
    await handler.handle_confession_interaction(
        interaction,
        confession,
        attachment_url,
        custom_color,
        attachment,
    )


@bot.tree.command(name="poll", description="Buat poll anonim")
@app_commands.describe(
    question="Pertanyaan poll",
    options="Opsi jawaban, pisahkan dengan koma (contoh: Opsi A, Opsi B, Opsi C) atau kosongkan untuk Yes/No",
    attachment="File foto opsional",
    attachment_url="URL attachment opsional",
    custom_color="Warna kustom opsional",
)
async def slash_poll(
    interaction: discord.Interaction,
    question: str,
    options: Optional[str] = None,
    attachment: Optional[discord.Attachment] = None,
    attachment_url: Optional[str] = None,
    custom_color: Optional[str] = None,
):
    parsed_options = None
    if options:
        parsed_options = [opt.strip() for opt in options.split(",") if opt.strip()]
        if not parsed_options:
            parsed_options = None

    await handler.handle_poll_interaction(
        interaction,
        question,
        attachment_url,
        custom_color,
        attachment,
        options=parsed_options,
    )


@bot.tree.command(name="confess_setup", description="Setup channel confession dan audit")
@app_commands.describe(
    confession_channel="Channel confession utama",
    audit_channel="Channel audit moderator (opsional)",
)
async def slash_confess_setup(
    interaction: discord.Interaction,
    confession_channel: discord.TextChannel,
    audit_channel: Optional[discord.TextChannel] = None,
):
    if not await ensure_mod_interaction(interaction):
        return
    if audit_channel is None:
        audit_channel = confession_channel
    handler.set_guild_channels(interaction.guild.id, confession_channel.id, audit_channel.id)
    await interaction.response.send_message(
        f"Setup selesai. Channel confession: {confession_channel.mention}, audit: {audit_channel.mention}",
        ephemeral=True,
    )


@bot.tree.command(name="confess_panel", description="Kirim panel confession ke channel confession")
async def slash_confess_panel(interaction: discord.Interaction):
    if not await ensure_mod_interaction(interaction):
        return

    confession_channel_id = handler.get_confession_channel_id(interaction.guild.id)
    if not confession_channel_id:
        await interaction.response.send_message(
            "Set channel dulu pakai /confess_setup.",
            ephemeral=True,
        )
        return

    confession_channel = interaction.guild.get_channel(confession_channel_id)
    if confession_channel is None:
        await interaction.response.send_message(
            "Confession channel tidak ditemukan. Jalankan setup ulang.",
            ephemeral=True,
        )
        return

    panel = discord.Embed(
        title="Confessions",
        description="Kirim confession anonim lewat tombol di bawah. Jangan bagikan data sensitif.",
        color=discord.Color.dark_blue(),
    )
    await confession_channel.send(embed=panel, view=handler.get_persistent_view())
    await interaction.response.send_message("Panel confession berhasil dipasang.", ephemeral=True)


@bot.tree.command(name="confess_close", description="Tutup confession sementara")
async def slash_confess_close(interaction: discord.Interaction):
    if not await ensure_mod_interaction(interaction):
        return
    handler.set_guild_open(interaction.guild.id, False)
    await interaction.response.send_message("Confession submission ditutup.", ephemeral=True)


@bot.tree.command(name="confess_open", description="Buka confession kembali")
async def slash_confess_open(interaction: discord.Interaction):
    if not await ensure_mod_interaction(interaction):
        return
    handler.set_guild_open(interaction.guild.id, True)
    await interaction.response.send_message("Confession submission dibuka.", ephemeral=True)


@bot.tree.command(name="confess_audit", description="Lihat pengirim confession berdasarkan ID")
@app_commands.describe(confession_id="Nomor confession/reply")
async def slash_confess_audit(interaction: discord.Interaction, confession_id: int):
    if not await ensure_mod_interaction(interaction):
        return

    user_id = handler._audit_map.get(confession_id)
    if not user_id:
        await interaction.response.send_message("Confession ID tidak ditemukan.", ephemeral=True)
        return

    member = interaction.guild.get_member(user_id)
    who = f"{member.mention} ({user_id})" if member else str(user_id)
    await interaction.response.send_message(
        f"Confession #{confession_id} dikirim oleh {who}",
        ephemeral=True,
    )

bot.run(TOKEN)