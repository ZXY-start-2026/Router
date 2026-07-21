import re


def make_title(content: str, max_chars: int = 30) -> str:
    normalized = re.sub(r"\s+", " ", content.strip())
    if not normalized:
        return "新会话"
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[:max_chars]}…"

