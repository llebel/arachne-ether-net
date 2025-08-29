import asyncio
import discord
from discord.ext import commands
from discord.utils import _ColourFormatter
from db import MessageStore
from scheduler import DailySummary
from summarizer import summarize
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
db_logger = logging.getLogger("db")
db_logger.setLevel(logging.DEBUG)

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
    logger.info(f"Populating database with {n_days} days of message history...")
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
# ✅ Commande manuelle pour déclencher le résumé
@bot.command(name="resume")
async def manual_resume(ctx, channel_name=None):
    """Command to generate a summary manually.
    
    Usage:
        !resume - Generate summary for current channel
        !resume channel_name - Generate summary for specified channel
        !resume all - Generate summaries for all active channels
    """
    # Check if user is authorized
    if ctx.author.id not in config.AUTHORIZED_USER_IDS:
        logger.warning(
            f"Unauthorized !resume attempt by {ctx.author} (ID: {ctx.author.id})"
        )
        return

    since = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    try:
        if channel_name == "all":
            # Generate summaries for all active channels
            active_channels = store.get_active_channels(since)
            if not active_channels:
                await ctx.send("📋 Aucun message trouvé depuis minuit dans aucun canal.")
                return
                
            summaries = []
            for channel in active_channels:
                messages = store.get_messages_since(since, channel)
                if messages:
                    summary = summarize(messages, channel)
                    summaries.append(f"**#{channel}** ({len(messages)} messages):\n{summary}")
            
            if summaries:
                full_summary = f"📋 Résumés de tous les canaux depuis le {since.date()} :\n\n" + "\n\n---\n\n".join(summaries)
                # Split if too long for Discord
                if len(full_summary) > 1800:
                    await ctx.send(f"📋 Résumés de tous les canaux depuis le {since.date()} :")
                    for summary_part in summaries:
                        await ctx.send(summary_part)
                else:
                    await ctx.send(full_summary)
            else:
                await ctx.send("📋 Aucun message à résumer depuis minuit.")
                
        else:
            # Generate summary for specific channel or current channel
            target_channel = channel_name or ctx.channel.name
            messages = store.get_messages_since(since, target_channel)
            
            if not messages:
                await ctx.send(f"📋 Aucun message trouvé depuis minuit dans #{target_channel}.")
                return
                
            summary = summarize(messages, target_channel)
            await ctx.send(f"📋 Résumé de #{target_channel} depuis le {since.date()} ({len(messages)} messages) :\n\n{summary}")
            
    except OpenAIError as e:
        logger.error(f"OpenAI error while generating summary: {e}")
        await ctx.send(f"⚠️ Impossible de générer le résumé pour l'instant : {str(e)}")
        return
    except Exception as e:
        logger.exception("Unexpected error in !resume command")
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
    Fetch messages from the last `days` days or since last fetch.
    """
    last_fetched = store.get_last_fetched(channel.name)
    after_date = last_fetched or (datetime.now(timezone.utc) - timedelta(days=days))

    logger.info(
        f"Fetching messages from #{channel.name} since {after_date.isoformat()}"
    )

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
