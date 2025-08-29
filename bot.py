import asyncio
import discord
from discord.ext import commands
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
logger.setLevel(logging.INFO)

# Only enable DEBUG for our db module
# db_logger = logging.getLogger("db")
# db_logger.setLevel(logging.DEBUG)

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

    # Fetch messages smartly
    n_days = 7
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
    store.add_message(
        str(message.author), message.content, message.channel.name, message.created_at
    )
    await bot.process_commands(message)


# ----------------------
# Commands
# ----------------------
# ✅ Manual command to trigger a summary generation
@bot.command(name="resume")
async def manual_resume(ctx, channel_name=None, period="today"):
    """Command to generate a summary manually.

    Usage:
        !resume - Generate summary for current channel (today only)
        !resume channel_name - Generate summary for specified channel (today only)
        !resume all - Generate summaries for all active channels (today only)
        !resume 3days - Summary for current channel from 3 days ago to now
        !resume channel_name 3days - Summary for specified channel from 3 days ago to now
        !resume all 7days - Summary for all channels from 7 days ago to now
    """
    # Check if user is authorized
    if ctx.author.id not in config.AUTHORIZED_USER_IDS:
        logger.warning(
            f"Unauthorized !resume attempt by {ctx.author} (ID: {ctx.author.id})"
        )
        return

    # Parse period parameter for days (e.g., "3days", "7days", "1day")
    days_back = None
    if period and period.endswith("days"):
        try:
            days_back = int(period[:-4])  # Remove "days" suffix
        except ValueError:
            await ctx.send("⚠️ Format invalide. Utilisez par exemple: !resume all 3days")
            return
    elif period and period.endswith("day"):
        try:
            days_back = int(period[:-3])  # Remove "day" suffix
        except ValueError:
            await ctx.send("⚠️ Format invalide. Utilisez par exemple: !resume all 1day")
            return
    elif channel_name and channel_name.endswith("days"):
        try:
            days_back = int(channel_name[:-4])  # Remove "days" suffix
            channel_name = None  # Reset channel to current channel
        except ValueError:
            await ctx.send("⚠️ Format invalide. Utilisez par exemple: !resume 3days")
            return
    elif channel_name and channel_name.endswith("day"):
        try:
            days_back = int(channel_name[:-3])  # Remove "day" suffix
            channel_name = None  # Reset channel to current channel
        except ValueError:
            await ctx.send("⚠️ Format invalide. Utilisez par exemple: !resume 1day")
            return

    # Determine time range based on parameters
    now = datetime.now(timezone.utc)

    if days_back:
        # Custom days back
        start_time = now - timedelta(days=days_back)
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now
        if days_back == 1:
            time_desc = f"des dernières 24 heures"
        else:
            time_desc = f"des {days_back} derniers jours"
        period_type = "range"
    else:
        # Today only (default)
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now
        time_desc = f"depuis le {start_time.date()}"
        period_type = "since"

    try:
        if channel_name == "all":
            # Generate summaries for all active channels
            if period_type == "range":
                active_channels = store.get_active_channels_in_range(
                    start_time, end_time
                )
            else:
                active_channels = store.get_active_channels(start_time)

            if not active_channels:
                await ctx.send(f"📋 Aucun message trouvé {time_desc} dans aucun canal.")
                return

            # Send initial "thinking" message
            thinking_msg = await ctx.send(
                f"⚙️ Génération des résumés pour {len(active_channels)} canaux..."
            )

            summaries = []
            total_messages = 0
            for i, channel in enumerate(active_channels):
                if period_type == "range":
                    messages = store.get_messages_in_range(
                        start_time, end_time, channel
                    )
                else:
                    messages = store.get_messages_since(start_time, channel)

                if messages:
                    total_messages += len(messages)
                    # Update progress
                    await thinking_msg.edit(
                        content=f"⚙️ Génération des résumés... ({i+1}/{len(active_channels)}) #{channel}"
                    )
                    summary = summarize(messages, channel)
                    summaries.append(
                        f"**#{channel}** ({len(messages)} messages):\n{summary}"
                    )

            # Delete thinking message
            await thinking_msg.delete()

            if summaries:
                header = f"📋 Résumés de tous les canaux {time_desc} ({total_messages} messages sur {len(active_channels)} canaux) :\n\n"
                full_summary = header + "\n\n---\n\n".join(summaries)

                # Use safe_send to handle long messages
                await safe_send(ctx, full_summary)
            else:
                await ctx.send(f"📋 Aucun message à résumer {time_desc}.")

        else:
            # Generate summary for specific channel or current channel
            target_channel = channel_name or ctx.channel.name

            if period_type == "range":
                messages = store.get_messages_in_range(
                    start_time, end_time, target_channel
                )
            else:
                messages = store.get_messages_since(start_time, target_channel)

            if not messages:
                await ctx.send(
                    f"📋 Aucun message trouvé {time_desc} dans #{target_channel}."
                )
                return

            # Send thinking message for single channel
            thinking_msg = await ctx.send(
                f"⚙️ Génération du résumé pour #{target_channel}..."
            )
            summary = summarize(messages, target_channel)
            await thinking_msg.delete()

            result_msg = f"📋 Résumé de #{target_channel} {time_desc} ({len(messages)} messages) :\n\n{summary}"
            await safe_send(ctx, result_msg)

    except OpenAIError as e:
        logger.error(f"OpenAI error while generating summary: {e}")
        # Try to delete thinking message if it exists
        try:
            await thinking_msg.delete()
        except:
            pass
        await ctx.send(f"⚠️ Impossible de générer le résumé pour l'instant : {str(e)}")
        return
    except Exception as e:
        logger.exception("Unexpected error in !resume command")
        # Try to delete thinking message if it exists
        try:
            await thinking_msg.delete()
        except:
            pass
        await ctx.send(f"⚠️ Une erreur inattendue est survenue : {str(e)}")
        return

    logger.info(
        f"Résumé envoyé par la commande !resume dans {ctx.guild} / {ctx.channel}"
    )


# ----------------------
# Utilities
# ----------------------
async def fetch_history(channel, days=7):
    """
    Fetch messages from Discord from the last `days` days or since last fetch known in DB.
    """
    last_fetched = store.get_last_fetched(channel.name)
    after_date = last_fetched or (datetime.now(timezone.utc) - timedelta(days=days))

    logger.info(
        f"Fetching Discord messages from #{channel.name} since {after_date.isoformat()}"
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
                )

        # Update last fetched timestamp
        store.update_last_fetched(channel.name, datetime.now(timezone.utc))
    except Exception as e:
        logger.warning(f"Failed to fetch messages from #{channel.name}: {e}")


# ----------------------
# Run bot
# ----------------------
bot.run(config.DISCORD_TOKEN)
