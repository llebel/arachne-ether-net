import openai
from openai import OpenAIError
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def summarize(messages):
    if not messages:
        return "Aucun message à résumer aujourd'hui."

    text = "\n".join([f"{author}: {content}" for author, content in messages])

    prompt = f"""
    Voici une conversation Discord de la journée :
    {text}

    Résume cette discussion de façon claire et concise (en français).
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        # ⚡ Use .content instead of ["content"]
        return response.choices[0].message.content.strip()

    except OpenAIError:
        return "⚠️ Impossible de générer le résumé pour l'instant (erreur OpenAI)."
