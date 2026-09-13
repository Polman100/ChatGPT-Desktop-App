from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from openai import OpenAI

from app_config import TITLE_MODEL


class ApiService:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def stream_chat(
        self,
        model: str,
        messages: list[dict[str, Any]]
    ) -> Iterator[str]:
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True
        )

        for chunk in response:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            token = delta.content or ""

            if token:
                yield token

    def generate_title(
        self,
        prompt: str,
        max_chars: int = 40
    ) -> str:
        trimmed_prompt = prompt[:1000]

        system_message = (
            "Jesteś pomocnym narzędziem, którego zadaniem jest "
            "wygenerowanie krótkiego tytułu dla konwersacji. "
            "Zwróć wyłącznie krótki tytuł, bez dodatkowych "
            "wyjaśnień, najlepiej do "
            f"{max_chars} znaków."
        )

        user_message = (
            "Na podstawie tej treści podaj krótką nazwę "
            "konwersacji. Tylko nazwa, bez cudzysłowów:\n\n"
            f'"{trimmed_prompt}"'
        )

        response = self.client.chat.completions.create(
            model=TITLE_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_message
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_completion_tokens=32,
            stream=False
        )

        content = response.choices[0].message.content or ""
        content = content.strip()
        content = content.splitlines()[0].strip()

        return content[:max_chars]

    def get_usage(
        self,
        start_date: str,
        end_date: str,
        usage_function
    ) -> float:
        return usage_function(
            start_date=start_date,
            end_date=end_date
        )