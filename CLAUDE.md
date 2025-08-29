# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Discord bot that automatically summarizes daily conversations using OpenAI's API. The bot stores messages in a SQLite database, generates daily summaries at a configurable time, and supports manual summary generation through a command.

## Architecture

- **bot.py**: Main Discord bot entry point with message handling, logging configuration, and commands
- **db.py**: SQLite database operations for message storage via `MessageStore` class
- **scheduler.py**: Daily summary scheduling using Discord.py's task loop (`DailySummary` class)
- **summarizer.py**: OpenAI integration for generating conversation summaries using GPT-4o-mini
- **config.py**: Environment variable configuration loading with dotenv support

## Key Features

- **Message Storage**: Automatically stores all non-bot messages with channel tracking
- **History Fetching**: Intelligently fetches message history on startup (7 days by default)
- **Daily Summaries**: Automated daily summaries at configured UTC hour
- **Manual Summaries**: `!resume` command for authorized users to generate summaries on demand
- **Comprehensive Logging**: File and console logging with configurable levels
- **Smart Channel Tracking**: Tracks last fetched timestamp per channel to avoid duplicates

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
- `SUMMARY_CHANNEL`: Discord channel name for summaries (default: "résumés") 
- `SUMMARY_HOUR`: UTC hour for daily summaries (default: 20)
- `AUTHORIZED_USER_IDS`: Comma-separated list of Discord user IDs authorized to use `!resume` command

## Database

The bot uses SQLite (`messages.db`) with two tables:
- **messages**: Stores message data (id, channel, author, content, timestamp)
- **channel_meta**: Tracks last fetched timestamp per channel for efficient history fetching

The database maintains message history and is not cleared after summaries (contrary to previous documentation).