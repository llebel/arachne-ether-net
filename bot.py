import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from discord.utils import _ColourFormatter
from db import MessageStore
from scheduler import DailySummary
from summarizer import summarize
from utils import safe_send
import config
from datetime import datetime, timezone, timedelta
from openai import OpenAIError
import logging


# ----------------------
# Logging configuration
# ----------------------
# Remove default handlers and set up our own
logging.getLogger().handlers = []

# Create handlers
file_handler = logging.FileHandler("bot.log")
console_handler = logging.StreamHandler()

# Set formatters
file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
color_formatter = _ColourFormatter()

file_handler.setFormatter(file_formatter)
console_handler.setFormatter(color_formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Set specific levels
logger = logging.getLogger(__name__)

# ----------------------
# Bot setup
# ----------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

store = MessageStore()
scheduler = DailySummary(bot)


# ----------------------
# Events
# ----------------------
@bot.event
async def on_ready():
    logger.info(f"{bot.user} est connecté.")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

    # Fetch messages smartly
    n_days = config.FETCH_NB_DAYS
    logger.info(
        f"Populating database with {n_days} days of message history if needed..."
    )
    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                await fetch_history(channel, days=n_days)
                await asyncio.sleep(1)  # respect rate limits
            except Exception as e:
                logger.warning(f"Could not fetch messages from #{channel.name}: {e}")
    logger.info(f"Populating database done")


# Start daily summary scheduler
@bot.event
async def on_connect():
    logger.info("Starting daily summary scheduler...")
    scheduler.run_daily_summary.start()


# Remember messages seen
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Get server and channel information
    server_id = str(message.guild.id) if message.guild else None
    server_name = message.guild.name if message.guild else None
    channel_id = str(message.channel.id)

    # Get category information
    category_id = str(message.channel.category_id) if message.channel.category else None
    category_name = message.channel.category.name if message.channel.category else None

    logger.info(
        f"Seen message on server {server_name}({server_id}) / category {category_name}({category_id}) / channel #{message.channel.name}({channel_id}) / user @{str(message.author)}"
    )
    store.add_message(
        str(message.author),
        message.content,
        message.channel.name,
        message.created_at,
        server_id=server_id,
        server_name=server_name,
        channel_id=channel_id,
    )
    await bot.process_commands(message)


# ----------------------
# Commands
# ----------------------
# ✅ Manual command to trigger a summary generation
@bot.tree.command(name="resume", description="Generate a conversation summary")
@app_commands.describe(
    channel="Channel to summarize ('current', 'all', or channel name)",
    days="Number of days to look back (default: today only)"
)
async def manual_resume(interaction: discord.Interaction, channel: str, days: int = 0):
    """Slash command to generate a summary manually."""
    
    # Check if user is authorized
    if interaction.user.id not in config.AUTHORIZED_USER_IDS:
        logger.warning(
            f"Unauthorized /resume attempt by {interaction.user} (ID: {interaction.user.id})"
        )
        await interaction.response.send_message("⚠️ Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        return

    # Defer the response since this will take time
    await interaction.response.defer()

    # Determine time range based on days parameter
    now = datetime.now(timezone.utc)
    
    if days > 0:
        # Custom days back
        start_time = now - timedelta(days=days)
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now
        if days == 1:
            time_desc = f"des dernières 24 heures"
        else:
            time_desc = f"des {days} derniers jours"
        period_type = "range"
    else:
        # Today only (default)
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now
        time_desc = f"depuis le {start_time.date()}"
        period_type = "since"

    # Get current server information
    server_id = str(interaction.guild.id) if interaction.guild else None
    server_name = interaction.guild.name if interaction.guild else None

    try:
        if channel == "all":
            # Generate summaries for all active channels in current server
            if period_type == "range":
                active_channels = store.get_active_channels_in_range(
                    start_time, end_time, server_id
                )
            else:
                active_channels = store.get_active_channels(start_time, server_id)

            if not active_channels:
                server_desc = f" sur {server_name}" if server_name else ""
                await interaction.followup.send(
                    f"📋 Aucun message trouvé {time_desc} dans aucun canal{server_desc}."
                )
                return

            # Send initial progress message
            await interaction.followup.send(
                f"⚙️ Génération des résumés pour {len(active_channels)} canaux sur {server_name}..."
            )

            summaries = []
            total_messages = 0
            for i, channel_name in enumerate(active_channels):
                if period_type == "range":
                    messages = store.get_messages_in_range(
                        start_time, end_time, channel_name=channel_name, server_id=server_id
                    )
                else:
                    messages = store.get_messages_since(
                        start_time, channel_name=channel_name, server_id=server_id
                    )

                if messages:
                    total_messages += len(messages)
                    # Get category information for this channel from channel_meta
                    _, category_name_cat = store.get_channel_category(
                        channel_name=channel_name, server_id=server_id
                    )
                    category_display = (
                        f" [{category_name_cat}]" if category_name_cat else ""
                    )

                    summary = summarize(messages, channel_name)
                    summaries.append(
                        f"**#{channel_name}**{category_display} ({len(messages)} messages):\n{summary}"
                    )

            if summaries:
                server_desc = f" sur **{server_name}**" if server_name else ""
                header = f"📋 Résumés de tous les canaux {time_desc}{server_desc} ({total_messages} messages sur {len(active_channels)} canaux) :\n\n"
                full_summary = header + "\n\n---\n\n".join(summaries)

                # Use safe_send to handle long messages
                await safe_send(interaction, full_summary)
            else:
                await interaction.followup.send(f"📋 Aucun message à résumer {time_desc}.")

        else:
            # Generate summary for specific channel or current channel in current server
            target_channel = interaction.channel.name if channel == "current" else channel

            if period_type == "range":
                messages = store.get_messages_in_range(
                    start_time,
                    end_time,
                    channel_name=target_channel,
                    server_id=server_id,
                )
            else:
                messages = store.get_messages_since(
                    start_time, channel_name=target_channel, server_id=server_id
                )

            if not messages:
                server_desc = f" sur {server_name}" if server_name else ""
                await interaction.followup.send(
                    f"📋 Aucun message trouvé {time_desc} dans #{target_channel}{server_desc}."
                )
                return

            # Send progress message
            await interaction.followup.send(
                f"⚙️ Génération du résumé pour #{target_channel}..."
            )
            summary = summarize(messages, target_channel)

            server_desc = f" sur **{server_name}**" if server_name else ""
            result_msg = f"📋 Résumé de #{target_channel} {time_desc}{server_desc} ({len(messages)} messages) :\n\n{summary}"
            await safe_send(interaction, result_msg)

    except OpenAIError as e:
        logger.error(f"OpenAI error while generating summary: {e}")
        await interaction.followup.send(f"⚠️ Impossible de générer le résumé pour l'instant : {str(e)}")
        return
    except Exception as e:
        logger.exception("Unexpected error in /resume command")
        await interaction.followup.send(f"⚠️ Une erreur inattendue est survenue : {str(e)}")
        return

    logger.info(
        f"Résumé envoyé par la commande /resume dans {interaction.guild} / {interaction.channel}"
    )


# ----------------------
# Utilities
# ----------------------
async def fetch_history(channel, days):
    """
    Fetch messages from Discord from the last `days` days or since last fetch known in DB.
    """
    # Get server and channel information
    server_id = str(channel.guild.id) if channel.guild else None
    server_name = channel.guild.name if channel.guild else None
    channel_id = str(channel.id)

    # Get category information
    category_id = str(channel.category_id) if channel.category else None
    category_name = channel.category.name if channel.category else None

    last_fetched = (
        store.get_last_fetched(channel_id, server_id, channel.name)
        if server_id
        else None
    )
    after_date = last_fetched or (datetime.now(timezone.utc) - timedelta(days=days))

    logger.info(
        f"Fetching messages|{server_name}|{category_name}|{category_id}|#{channel.name}|{channel_id}|{after_date.isoformat()}"
    )

    # Pulling message history from Discord
    try:
        async for message in channel.history(limit=None, after=after_date):
            if not message.author.bot:
                store.add_message(
                    str(message.author),
                    message.content,
                    channel.name,
                    message.created_at,
                    server_id=server_id,
                    server_name=server_name,
                    channel_id=channel_id,
                )

        # Update last fetched timestamp (including category info for channel metadata)
        if server_id:
            store.update_last_fetched(
                channel_id,
                datetime.now(timezone.utc),
                server_id,
                server_name,
                channel.name,
                category_id,
                category_name,
            )
    except Exception as e:
        logger.warning(
            f"Failed fetching  |{server_name}|{category_name}|{category_id}|#{channel.name}|{channel_id}: {e}"
        )


# ----------------------
# Run bot
# ----------------------
bot.run(config.DISCORD_TOKEN)
