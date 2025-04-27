from openai import OpenAI
import anthropic
from src.spotycli.config import settings


BASE_PERPLEXITY_URL = "https://api.perplexity.ai"
ANTHROPIC_MAX_TOKENS = 10240


def get_perplexity_report(system_prompt: str, user_prompt: str, model: str):
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {   
            "role": "user",
            "content": user_prompt,
        },
    ]

    client = OpenAI(api_key=settings.perplexity_api_key, base_url=BASE_PERPLEXITY_URL)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    citations = response.citations
    message = response.choices[0].message
    return message.content, citations


def get_anthropic_report(system_prompt: str, user_prompt: str, model: str, max_tokens: int = ANTHROPIC_MAX_TOKENS):
    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
    )

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )
    message = response.content[0]
    return message.text, message.citations
