"""
Abstract base classes for question handling.
Define interfaces for: QuestionHandler (select/radio/text/textarea),
AnswerMatcher (label -> answer).
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from selenium.webdriver.remote.webelement import WebElement

class QuestionHandler(ABC):
    """Handles a specific question type (select, radio, text, textarea)."""
    @abstractmethod
    def answer(self, question_element: WebElement, answer: str) -> bool:
        """Attempt to set the answer. Return success boolean."""
        pass

    @abstractmethod
    def get_label(self, question_element: WebElement) -> Optional[str]:
        """Extract the label text from the question element."""
        pass

class AnswerMatcher(ABC):
    """Matches a question label to an answer string."""
    @abstractmethod
    def match(self, label: str, question_type: str, context: Dict[str, Any]) -> Optional[str]:
        """
        Return the answer string if this matcher can provide one, else None.
        context may contain job description, options list, etc.
        """
        pass