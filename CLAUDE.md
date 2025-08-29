# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Discord bot that automatically summarizes daily conversations using OpenAI's API. The bot stores messages in a SQLite database with full server and channel hierarchy support, generates daily summaries at a configurable time, and supports manual summary generation through commands. The bot handles multiple Discord servers simultaneously with proper isolation and category-aware organization.

## Architecture

- **bot.py**: Main Discord bot entry point with message handling, logging configuration, and commands. Includes server/category/channel hierarchy tracking and automatic message history population.
- **db.py**: SQLite database operations via `MessageStore` class with server-aware schema, automatic migrations, and efficient channel metadata management
- **scheduler.py**: Daily summary scheduling using Discord.py's task loop (`DailySummary` class) with per-server processing and category-aware formatting
- **summarizer.py**: OpenAI integration for generating conversation summaries using GPT-5-mini (via Responses API) with comprehensive INFO logging
- **config.py**: Environment variable configuration loading with dotenv support including history fetching configuration

## Key Features

- **Multi-Server Support**: Full isolation between Discord servers with server-specific summaries
- **Message Storage**: Stores all non-bot messages with complete server/channel/category hierarchy
- **Channel ID Tracking**: Uses Discord's unique channel IDs to handle channel name conflicts across servers and categories
- **Category Organization**: Displays channel categories in summaries for better context and organization
- **History Fetching**: Intelligently fetches configurable days of message history on startup with per-channel tracking
- **Daily Summaries**: Automated server-specific daily summaries posted to each server's designated summary channel
- **Manual Summaries**: `!resume` command with server isolation and category display for authorized users
- **Comprehensive Logging**: Detailed file and console logging including message tracking with full hierarchy context
- **Smart Channel Tracking**: Per-channel last-fetched timestamps using unique channel IDs to avoid duplicates
- **Automatic Migrations**: Database schema evolves automatically with backward compatibility

## Development Commands

### Environment Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
# For development dependencies:
pip install -r requirements-dev.txt
```

### Running the Bot
```bash
# Copy environment template
cp .env.example .env
# Edit .env with your Discord token, OpenAI API key, and authorized user IDs

# Run the bot
python bot.py
```

## Configuration

Required environment variables in `.env`:
- `DISCORD_TOKEN`: Discord bot token
- `OPENAI_API_KEY`: OpenAI API key for summaries
- `SUMMARY_CHANNEL`: Discord channel name for summaries (default: "résumés") - bot will look for this channel in each server
- `SUMMARY_HOUR`: UTC hour for daily summaries (default: 20)
- `AUTHORIZED_USER_IDS`: Comma-separated list of Discord user IDs authorized to use `!resume` command
- `FETCH_NB_DAYS`: Number of days of message history to fetch on startup (default: 7)

## Database Schema

The bot uses SQLite (`messages.db`) with two main tables:

### messages
Stores individual message data with server context:
- `id`: Auto-incrementing primary key
- `server_id`: Discord server (guild) ID for isolation
- `server_name`: Human-readable server name
- `channel_id`: Discord channel ID (unique identifier)
- `channel_name`: Human-readable channel name
- `author`: Message author username
- `content`: Message text content
- `timestamp`: Message creation timestamp (ISO format)

### channel_meta
Tracks channel metadata and fetching state:
- `server_id`: Discord server ID
- `server_name`: Human-readable server name
- `channel_id`: Discord channel ID (unique identifier)
- `channel_name`: Human-readable channel name
- `category_id`: Discord category ID (if channel is in a category)
- `category_name`: Human-readable category name
- `last_fetched`: Timestamp of last message fetch for this channel
- Primary key: `(server_id, channel_id)`

## Key Design Decisions

- **Server Isolation**: All data is partitioned by Discord server to handle multi-server deployments
- **Channel IDs**: Uses Discord's unique channel IDs instead of names to handle conflicts and renames  
- **Category at Channel Level**: Category information stored in `channel_meta` only, not duplicated per message
- **Automatic Migrations**: Schema evolves automatically with backward compatibility for existing databases
- **Message History Preservation**: Messages are never deleted, maintaining complete conversation history

## Bot Behavior

### Startup Process
1. **Connection**: Bot connects to Discord and logs server information
2. **History Population**: Fetches `FETCH_NB_DAYS` of message history from all accessible text channels across all servers
3. **Channel Metadata**: Updates `channel_meta` with current channel information including categories
4. **Daily Scheduler**: Starts the automated daily summary task loop

### Message Handling
- **Real-time Storage**: Every non-bot message is immediately stored with full server/channel/category context
- **Logging**: Each message logs server, category, channel, and user information for debugging
- **Rate Limiting**: Respects Discord rate limits with built-in delays during history fetching

### Daily Summaries
- **Per-Server Processing**: Each server gets its own summary posted to its designated summary channel
- **Category Display**: Channel summaries include category information for better organization
- **Concurrent Servers**: Multiple servers are processed simultaneously during the daily summary cycle
- **Progress Indication**: Shows progress messages while generating summaries

### Manual Summaries (`!resume` command)
- **Server Isolation**: Only processes channels from the current server where command is executed
- **Category Context**: Displays category information alongside channel names in summaries
- **Flexible Time Ranges**: Supports custom day ranges (e.g., `!resume all 7days`)
- **Authorization**: Only users in `AUTHORIZED_USER_IDS` can execute the command

## Database Methods

Key methods in `MessageStore` class:
- `add_message()`: Store new messages with server/channel context
- `get_messages_since()` / `get_messages_in_range()`: Retrieve messages with server/channel filtering
- `get_channel_category()`: Get category information for a channel from metadata
- `get_active_channels()` / `get_active_channels_in_range()`: Find channels with recent activity
- `get_servers()`: List all servers with stored messages
- `update_last_fetched()`: Track channel history fetching state with category information

## Logging

The bot uses comprehensive logging:
- **File Logging**: `logs/discord_bot.log` with daily rotation
- **Console Logging**: Real-time output for monitoring
- **Message Tracking**: Each message logs full server/category/channel hierarchy
- **Summary Operations**: Detailed logging of summary generation and API calls
- **Error Handling**: Comprehensive error logging for debugging