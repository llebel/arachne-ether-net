from openai import OpenAI
from openai._exceptions import OpenAIError
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

def summarize(messages, channel_name=None):
    if not messages:
        return "Aucun message à résumer aujourd'hui."

    text = "\n".join([f"{author}: {content}" for author, content in messages])
    
    channel_context = f" du canal #{channel_name}" if channel_name else ""

    prompt = f"""
    Voici une conversation Discord{channel_context} de la journée :
    {text}

    Résume cette discussion de façon claire et concise (en français).
    """

    try:
        response = client.responses.create(
            model="gpt-5-mini",
            input=prompt,
            max_output_tokens=1000,
        )
        # ⚡ Use the Responses API format
        return response.output_text.strip()

    except OpenAIError:
        return "⚠️ Impossible de générer le résumé pour l'instant (erreur OpenAI)."
