"""
Built-in answer matchers.
Each matcher takes a label, question type, and context, returns answer or None.
"""

import re
import logging
from typing import Optional, Dict, Any
from thefuzz import fuzz  # optional fuzzy matching
from config.loader import resolve_placeholders  # temporary helper for resolving from defaults

logger = logging.getLogger("AutoApply.Matchers")

class KeywordMatcher:
    """
    Matches using a dictionary of predefined answers (from defaults.yaml).
    Answers are loaded from config at init.
    """
    def __init__(self, answers_dict: Dict[str, str]):
        self.answers = answers_dict  # flat mapping from lowercased label pattern to answer

    def match(self, label: str, question_type: str, context: Dict[str, Any]) -> Optional[str]:
        """Look for an exact or partial keyword in the label."""
        label_lower = label.lower()
        # Check direct key
        for pattern, answer in self.answers.items():
            if pattern.lower() in label_lower or label_lower in pattern.lower():
                logger.debug(f"KeywordMatcher: '{label}' -> '{answer}' (matched {pattern})")
                return answer
        return None

class RegexMatcher:
    """Matches using regular expression patterns."""
    patterns = {
        r".*\byears\s+of\s+experience\b.*": "%YEARS_EXPERIENCE%",
        r".*\bexperience\s+in\s+(.*)\b.*": "%YEARS_EXPERIENCE%",  # fallback
        r".*\bnotice\s+period\b.*": "%NOTICE_PERIOD%",
        r".*\bdesired\s+salary\b.*": "%DESIRED_SALARY%",
        r".*\bcurrent\s+ctc\b.*": "%CURRENT_CTC%",
    }

    def match(self, label: str, question_type: str, context: Dict[str, Any]) -> Optional[str]:
        label_lower = label.lower()
        for pattern, placeholder in self.patterns.items():
            if re.match(pattern, label, re.IGNORECASE):
                # Resolve placeholder from user data
                resolved = resolve_placeholders(placeholder, context.get("user_data", {}))
                logger.debug(f"RegexMatcher: '{label}' -> '{resolved}'")
                return resolved
        return None

class FuzzyMatcher:
    """
    Uses fuzzy string matching against a list of known labels.
    Only returns answer if confidence exceeds threshold.
    """
    def __init__(self, known_answers: Dict[str, str], threshold: int = 80):
        self.known_answers = known_answers  # label: answer
        self.threshold = threshold

    def match(self, label: str, question_type: str, context: Dict[str, Any]) -> Optional[str]:
        best_score = 0
        best_answer = None
        for known_label, answer in self.known_answers.items():
            score = fuzz.partial_ratio(label.lower(), known_label.lower())
            if score > best_score:
                best_score = score
                best_answer = answer
        if best_score >= self.threshold:
            logger.debug(f"FuzzyMatcher: '{label}' -> '{best_answer}' (score {best_score})")
            return best_answer
        return None

class FakerFallbackMatcher:
    """If enabled, returns a fake answer using faker."""
    def match(self, label: str, question_type: str, context: Dict[str, Any]) -> Optional[str]:
        from utils.faker_fill import generate_fake_answer
        return generate_fake_answer(label)