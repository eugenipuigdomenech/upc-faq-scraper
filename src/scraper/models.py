from dataclasses import dataclass
from typing import Any


@dataclass
class FaqItem:
    id: str
    topic: str
    topic_subtitle: str
    question: str
    answer: str
    source: str
    approved_var: Any
