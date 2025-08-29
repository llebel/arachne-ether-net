"""Shared utility functions for the Discord bot."""


async def safe_send(channel, content, max_length=1900):
    """Safely send a message, splitting if too long for Discord's 2000 char limit."""
    if len(content) <= max_length:
        await channel.send(content)
        return

    # Split the content intelligently
    lines = content.split("\n")
    current_chunk = ""

    for line in lines:
        # If adding this line would exceed limit, send current chunk
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                await channel.send(current_chunk.strip())
                current_chunk = line + "\n"
            else:
                # Single line is too long, truncate it
                truncated_line = line[: max_length - 20] + "... [tronqué]"
                await channel.send(truncated_line)
        else:
            current_chunk += line + "\n"

    # Send remaining chunk
    if current_chunk:
        await channel.send(current_chunk.strip())
