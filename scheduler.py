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
            midnight = get_midnight_utc()
            active_channels = store.get_active_channels(midnight)
            
            summary_channel = discord.utils.get(self.bot.get_all_channels(), name=SUMMARY_CHANNEL)
            if not summary_channel:
                print(f"❌ Summary channel '{SUMMARY_CHANNEL}' not found!")
                return
            
            if not active_channels:
                await summary_channel.send(f"📋 Aucune activité détectée le {now.date()}")
                return
            
            # Generate per-channel summaries
            summaries = []
            total_messages = 0
            
            for channel_name in active_channels:
                messages = store.get_messages_since(midnight, channel_name)
                if messages:
                    total_messages += len(messages)
                    summary = summarize(messages, channel_name)
                    summaries.append(f"**#{channel_name}** ({len(messages)} messages):\n{summary}")
            
            if summaries:
                header = f"📋 Résumé quotidien du {now.date()} ({total_messages} messages sur {len(active_channels)} canaux) :\n\n"
                
                # Send summaries, splitting if too long
                if len(header + "\n\n---\n\n".join(summaries)) > 1800:
                    await summary_channel.send(header.rstrip())
                    for summary_part in summaries:
                        await summary_channel.send(summary_part)
                else:
                    full_summary = header + "\n\n---\n\n".join(summaries)
                    await summary_channel.send(full_summary)
            else:
                await summary_channel.send(f"📋 Aucun message à résumer le {now.date()}")
            
            # Note: We don't clear messages anymore to maintain history
