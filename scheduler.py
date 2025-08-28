from discord.ext import tasks
from datetime import datetime, timedelta, timezone
from db import MessageStore
from summarizer import summarize
import discord
import pytz
from config import SUMMARY_CHANNEL, SUMMARY_HOUR

store = MessageStore()

def get_midnight_utc():
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day)

class DailySummary:
    def __init__(self, bot):
        self.bot = bot

    @tasks.loop(minutes=1)
    async def run_daily_summary(self):
        now = datetime.now(timezone.utc)
        if now.hour == SUMMARY_HOUR and now.minute == 0:  # à XXh00 UTC
            messages = store.get_messages_since(get_midnight_utc())
            summary = summarize(messages)

            channel = discord.utils.get(self.bot.get_all_channels(), name=SUMMARY_CHANNEL)
            if channel:
                await channel.send(f"📋 Résumé du {now.date()} :\n\n{summary}")

            store.clear_messages()
