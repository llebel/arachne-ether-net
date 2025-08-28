import os
from dotenv import load_dotenv

# Charger le fichier .env
load_dotenv()

# Récupérer les variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUMMARY_CHANNEL = os.getenv("SUMMARY_CHANNEL", "résumés")  # valeur par défaut
SUMMARY_HOUR = int(os.getenv("SUMMARY_HOUR", 20))  # valeur par défaut: 20h UTC
