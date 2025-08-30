"""Shared utility functions for the Discord bot."""

import discord
from discord.ext import commands


async def safe_send(destination, content, max_length=1900):
    """Safely send a message, splitting if too long for Discord's 2000 char limit.
    
    Args:
        destination: Can be a channel, context, or interaction
        content: The message content to send
        max_length: Maximum length per message chunk
    """
    async def _send_message(msg):
        """Send a message using the appropriate method."""
        if isinstance(destination, discord.Interaction):
            await destination.followup.send(msg)
        elif isinstance(destination, commands.Context):
            await destination.send(msg)
        else:
            # Assume it's a channel or similar
            await destination.send(msg)
    
    if len(content) <= max_length:
        await _send_message(content)
        return

    # Split the content intelligently
    lines = content.split("\n")
    current_chunk = ""

    for line in lines:
        # If adding this line would exceed limit, send current chunk
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                await _send_message(current_chunk.strip())
                current_chunk = line + "\n"
            else:
                # Single line is too long, truncate it
                truncated_line = line[: max_length - 20] + "... [tronqué]"
                await _send_message(truncated_line)
        else:
            current_chunk += line + "\n"

    # Send remaining chunk
    if current_chunk:
        await _send_message(current_chunk.strip())
