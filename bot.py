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
async def manual_resume(ctx):
    """Command to generate a summary manually."""
    # Check if user is authorized
    if ctx.author.id != config.AUTHORIZED_USER_ID:
        logger.warning(
            f"Unauthorized !resume attempt by {ctx.author} (ID: {ctx.author.id})"
        )
        return

    since = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    messages = store.get_messages_since(since)

    try:
        summary = summarize(messages)
    except OpenAIError as e:
        logger.error(f"OpenAI error while generating summary: {e}")
        await ctx.send(f"⚠️ Impossible de générer le résumé pour l'instant : {str(e)}")
        return
    except Exception as e:
        logger.exception("Unexpected error in !resume command")
        await ctx.send(f"⚠️ Une erreur inattendue est survenue : {str(e)}")
        return

    # Envoyer le résumé dans Discord
    await ctx.send(f"📋 Résumé demandé :\n\n{summary}")
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
