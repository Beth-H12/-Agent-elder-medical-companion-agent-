import re
from typing import Iterable, List, Optional


def extract_first_match(text: str, keywords: Iterable[str]) -> Optional[str]:
    for keyword in keywords:
        if keyword in text:
            return keyword
    return None


def extract_date(text: str) -> Optional[str]:
    match = re.search(r"(20\d{2}[-/]\d{2}[-/]\d{2})", text)
    if not match:
        return None
    return match.group(1).replace("/", "-")


def normalize_lines(text: str) -> List[str]:
    lines = [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
    return lines[:8]
