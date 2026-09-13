from __future__ import annotations

from pathlib import Path
from typing import Any
import datetime
import json
import os
import re
import threading
import unicodedata


class ConversationStorage:
    def __init__(self, history_dir: Path):
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.file_lock = threading.Lock()

    @staticmethod
    def remove_diacritics(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)

        return "".join(
            char
            for char in normalized
            if not unicodedata.combining(char)
        )

    @classmethod
    def sanitize_filename(cls, value: str) -> str:
        value = value.strip()
        value = value.replace("\n", " ")
        value = cls.remove_diacritics(value)

        value = re.sub(
            r"[^A-Za-z0-9 _-]",
            "",
            value
        )

        value = value[:40].strip()

        return value or "conversation"

    def make_unique_filename(self, base_name: str) -> Path:
        candidate = self.history_dir / f"{base_name}.txt"
        counter = 1

        while candidate.exists():
            candidate = (
                self.history_dir
                / f"{base_name} ({counter}).txt"
            )
            counter += 1

        return candidate

    def create_filename_from_prompt(self, prompt: str) -> Path:
        now = datetime.datetime.now()

        date_part = now.strftime("%Y.%m.%d")
        time_part = now.strftime("%H%M")

        words = prompt.strip().split()
        short_title = self.sanitize_filename(
            " ".join(words[:10])
            if words
            else "conversation"
        )

        base_name = f"{date_part} {time_part} - {short_title}"

        return self.make_unique_filename(base_name)

    def save(
        self,
        path: Path,
        messages: list[dict[str, Any]]
    ) -> None:
        path = Path(path)
        temporary_path = path.with_suffix(path.suffix + ".tmp")

        with self.file_lock:
            with temporary_path.open(
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(
                    messages,
                    file,
                    ensure_ascii=False,
                    indent=2
                )

            os.replace(temporary_path, path)

    def load(self, path: Path) -> list[dict[str, Any]]:
        with Path(path).open(
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError(
                "Nieprawidłowy format pliku rozmowy."
            )

        return data

    def list_files(self) -> list[Path]:
        files = [
            path
            for path in self.history_dir.iterdir()
            if path.is_file()
        ]

        return sorted(
            files,
            key=lambda path: path.stat().st_mtime,
            reverse=True
        )

    def delete(self, path: Path) -> None:
        Path(path).unlink(missing_ok=True)