import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Read corresponding variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUMMARY_CHANNEL = os.getenv("SUMMARY_CHANNEL", "summaries")  # default value
SUMMARY_HOUR = int(os.getenv("SUMMARY_HOUR", 20))  # default value: 20h UTC
FETCH_NB_DAYS = int(os.getenv("FETCH_NB_DAYS", 7))  # default value: 7 days
AUTHORIZED_USER_IDS = [
    int(user_id.strip())
    for user_id in os.getenv("AUTHORIZED_USER_IDS", "0").split(",")
    if user_id.strip()
]  # Discord user IDs for !resume command (comma-separated)
