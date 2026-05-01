"""
Question router: takes a WebElement (question) and determines the answer using a chain of matchers.
If no answer found, applies the configured unknown action (pause, skip, fill).
"""

import logging
from typing import Optional, Dict, Any, List
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver

from question_handling.base import AnswerMatcher
from core.state import state

logger = logging.getLogger("AutoApply.QuestionRouter")

class QuestionRouter:
    """
    Routes a question to the appropriate handler and matcher.
    """
    def __init__(self, matchers: List[AnswerMatcher], handlers: Dict[str, object],
                 unknown_action: str = "pause", user_pause_callback=None):
        self.matchers = matchers
        self.handlers = handlers
        self.unknown_action = unknown_action
        self.user_pause_callback = user_pause_callback  # for pausing and getting user input

    def answer_question(self, question_element: WebElement, job_context: dict) -> Optional[str]:
        """
        Determine answer and apply it. Returns the answer string if successful, None if skipped/failed.
        """
        # First identify question type
        question_type = self._detect_question_type(question_element)
        handler = self.handlers.get(question_type)
        if not handler:
            logger.warning(f"No handler for question type {question_type}")
            return None

        label = handler.get_label(question_element) or "Unknown"
        prev_answer = handler.get_current_value(question_element) if hasattr(handler, 'get_current_value') else None

        # If overwrite off and answer exists, use it
        if not state.settings.get("behaviour", {}).get("overwrite_previous_answers", False) and prev_answer:
            logger.debug(f"Previous answer exists and overwrite disabled: {label} = {prev_answer}")
            return prev_answer

        # Build context
        context = {
            "user_data": state.settings.get("user", {}),
            "job_description": job_context.get("description", ""),
            "options": handler.get_options(question_element) if hasattr(handler, 'get_options') else [],
        }

        # Try matchers
        answer = None
        for matcher in self.matchers:
            answer = matcher.match(label, question_type, context)
            if answer:
                break

        if not answer:
            # No matcher found, apply unknown action
            answer = self._handle_unknown(label, question_type, context)

        if answer:
            success = handler.answer(question_element, answer)
            if success:
                logger.info(f"Answered: '{label}' ({question_type}) -> '{answer}'")
                return answer
            else:
                logger.error(f"Failed to set answer for '{label}' with '{answer}'")
                return None
        return None

    def _handle_unknown(self, label: str, question_type: str, context: dict) -> Optional[str]:
        """Handle unknown questions based on setting."""
        action = state.unknown_action
        if action == "pause":
            if self.user_pause_callback:
                # Allow user to intervene
                return self.user_pause_callback(label, question_type, context)
            return None
        elif action == "skip_job":
            raise Exception("skip_job")  # caught higher up to skip this application
        elif action == "fill_placeholder":
            return "N/A"
        elif action == "fill_random":
            matcher = FakerFallbackMatcher()
            return matcher.match(label, question_type, context)
        return "N/A"  # fallback

    def _detect_question_type(self, element: WebElement) -> str:
        """Identify if it's select, radio, text, or textarea."""
        if element.find_element(By.XPATH, ".//select"):
            return "select"
        if element.find_element(By.XPATH, ".//fieldset[@data-test-form-builder-radio-button-form-component='true']"):
            return "radio"
        if element.find_element(By.XPATH, ".//input[@type='text']"):
            return "text"
        if element.find_element(By.XPATH, ".//textarea"):
            return "textarea"
        return "unknown"