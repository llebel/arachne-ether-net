# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Discord bot that automatically summarizes daily conversations using OpenAI's API. The bot stores messages in a SQLite database and generates daily summaries at a configurable time.

## Architecture

- **bot.py**: Main Discord bot entry point and message handling
- **db.py**: SQLite database operations for message storage via `MessageStore` class
- **scheduler.py**: Daily summary scheduling using Discord.py's task loop (`DailySummary` class)
- **summarizer.py**: OpenAI integration for generating conversation summaries
- **config.py**: Environment variable configuration loading

## Development Commands

### Environment Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements-dev.txt
```

### Running the Bot
```bash
# Copy environment template
cp .env.example .env
# Edit .env with your Discord token and OpenAI API key

# Run the bot
python bot.py
```

## Configuration

Required environment variables in `.env`:
- `DISCORD_TOKEN`: Discord bot token
- `OPENAI_API_KEY`: OpenAI API key for summaries
- `SUMMARY_CHANNEL`: Discord channel name for summaries (default: "résumés") 
- `SUMMARY_HOUR`: UTC hour for daily summaries (default: 20)

## Database

The bot uses SQLite (`messages.db`) with a single table storing:
- Message author
- Message content  
- Timestamp

Messages are automatically cleared after each daily summary.