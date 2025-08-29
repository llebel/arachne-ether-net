from discord.ext import tasks
from datetime import datetime, timedelta, timezone
from db import MessageStore
from summarizer import summarize
from utils import safe_send
import discord
from config import SUMMARY_CHANNEL, SUMMARY_HOUR

store = MessageStore()


def get_midnight_utc():
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day)


def get_summary_time_range():
    """Return start and end datetime for summary period:
    - Start: Beginning of previous day (00:00 yesterday)
    - End: Current summary hour today
    """
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    # Start of previous day (00:00 yesterday)
    start_time = datetime(
        yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc
    )

    # Current day up to summary hour
    end_time = datetime(now.year, now.month, now.day, SUMMARY_HOUR, tzinfo=timezone.utc)

    return start_time, end_time


class DailySummary:
    def __init__(self, bot):
        self.bot = bot

    @tasks.loop(minutes=1)
    async def run_daily_summary(self):
        now = datetime.now(timezone.utc)
        if now.hour == SUMMARY_HOUR and now.minute == 0:  # à XXh00 UTC
            start_time, end_time = get_summary_time_range()
            
            # Get all servers with activity and process each separately
            active_channels_all_servers = store.get_active_channels_in_range(start_time, end_time)
            
            if not active_channels_all_servers:
                # Try to find any summary channel to send "no activity" message
                summary_channel = discord.utils.get(
                    self.bot.get_all_channels(), name=SUMMARY_CHANNEL
                )
                if summary_channel:
                    yesterday = now - timedelta(days=1)
                    await summary_channel.send(
                        f"📋 Aucune activité détectée du {yesterday.date()} au {now.date()} jusqu'à {SUMMARY_HOUR}h"
                    )
                return
            
            # Group channels by server
            servers = {}
            for server_id, server_name, channel_name in active_channels_all_servers:
                if server_id not in servers:
                    servers[server_id] = {'name': server_name, 'channels': []}
                servers[server_id]['channels'].append(channel_name)
            
            # Generate summaries for each server
            for server_id, server_data in servers.items():
                server_name = server_data['name']
                active_channels = server_data['channels']
                
                # Find summary channel for this specific server
                summary_channel = None
                for channel in self.bot.get_all_channels():
                    if (channel.name == SUMMARY_CHANNEL and 
                        channel.guild and str(channel.guild.id) == server_id):
                        summary_channel = channel
                        break
                
                if not summary_channel:
                    print(f"❌ Summary channel '{SUMMARY_CHANNEL}' not found on server {server_name}!")
                    continue

                # Generate per-channel summaries for this server
                summaries = []
                total_messages = 0
                yesterday = now - timedelta(days=1)

                # Send initial thinking message
                thinking_msg = None
                if summary_channel:
                    thinking_msg = await summary_channel.send(
                        f"⚙️ Génération des résumés quotidiens pour {len(active_channels)} canaux sur {server_name}..."
                    )

                for i, channel_name in enumerate(active_channels):
                    messages = store.get_messages_in_range(
                        start_time, end_time, channel_name, server_id
                    )
                    if messages:
                        total_messages += len(messages)
                        # Update progress
                        if thinking_msg:
                            try:
                                await thinking_msg.edit(
                                    content=f"⚙️ Génération des résumés quotidiens... ({i+1}/{len(active_channels)}) #{channel_name}"
                                )
                            except:
                                pass  # Message might have been deleted
                        summary = summarize(messages, channel_name)
                        summaries.append(
                            f"**#{channel_name}** ({len(messages)} messages):\n{summary}"
                        )

                # Delete thinking message
                if thinking_msg:
                    try:
                        await thinking_msg.delete()
                    except:
                        pass

                if summaries:
                    header = f"📋 Résumé du {yesterday.date()} au {now.date()} jusqu'à {SUMMARY_HOUR}h sur **{server_name}** ({total_messages} messages sur {len(active_channels)} canaux) :\n\n"
                    full_summary = header + "\n\n---\n\n".join(summaries)

                    # Use safe_send to handle long messages
                    await safe_send(summary_channel, full_summary)
                else:
                    await summary_channel.send(
                        f"📋 Aucun message à résumer du {yesterday.date()} au {now.date()} jusqu'à {SUMMARY_HOUR}h sur {server_name}"
                    )

            # Note: We don't clear messages anymore to maintain history
