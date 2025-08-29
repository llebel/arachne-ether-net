import logging
from openai import OpenAI
from openai._exceptions import OpenAIError
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)
logger = logging.getLogger(__name__)


def summarize(messages, channel_name=None):
    logger.info(f"Starting summarize for {len(messages) if messages else 0} messages from channel: {channel_name or 'unknown'}")
    
    if not messages:
        logger.info("No messages to summarize, returning early")
        return "Aucun message à résumer aujourd'hui."

    text = "\n".join([f"{author}: {content}" for author, content in messages])
    logger.info(f"Prepared text for summarization ({len(text)} characters)")

    channel_context = f" du canal #{channel_name}" if channel_name else ""

    prompt = f"""
    Voici une conversation Discord{channel_context} de la journée :
    {text}

    Résume cette discussion de façon claire et concise (en français).
    """

    try:
        logger.info("Calling OpenAI API for summary generation")
        response = client.responses.create(
            model="gpt-5-mini",
            input=prompt,
            max_output_tokens=1000,
        )
        # ⚡ Use the Responses API format
        summary = response.output_text.strip()
        logger.info(f"Successfully generated summary ({len(summary)} characters)")
        return summary

    except OpenAIError as e:
        logger.info(f"OpenAI API error during summary generation: {e}")
        return "⚠️ Impossible de générer le résumé pour l'instant (erreur OpenAI)."
