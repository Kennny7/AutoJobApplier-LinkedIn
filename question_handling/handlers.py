"""
Concrete handlers for each question type: select, radio, text, textarea.
Inputs: Selenium WebElement representing the question form element.
Outputs: set answer on the page; return success boolean.
"""

import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException

from question_handling.base import QuestionHandler

logger = logging.getLogger("AutoApply.Handlers")

class SelectHandler(QuestionHandler):
    def get_label(self, element: WebElement) -> str:
        try:
            label = element.find_element(By.TAG_NAME, "label")
            return label.find_element(By.TAG_NAME, "span").text
        except NoSuchElementException:
            return "Unknown"

    def get_options(self, element: WebElement) -> list:
        select = Select(element.find_element(By.TAG_NAME, "select"))
        return [opt.text for opt in select.options]

    def answer(self, element: WebElement, answer: str) -> bool:
        try:
            select = Select(element.find_element(By.TAG_NAME, "select"))
            try:
                select.select_by_visible_text(answer)
                logger.debug(f"Select set to '{answer}'")
            except NoSuchElementException:
                # Try partial match
                for option in select.options:
                    if answer.lower() in option.text.lower() or option.text.lower() in answer.lower():
                        select.select_by_visible_text(option.text)
                        logger.debug(f"Select set to '{option.text}' via fuzzy")
                        return True
                return False
            return True
        except Exception:
            return False

class RadioHandler(QuestionHandler):
    def get_label(self, element: WebElement) -> str:
        try:
            title = element.find_element(By.XPATH, './/span[@data-test-form-builder-radio-button-form-component__title]')
            return title.text
        except NoSuchElementException:
            return "Unknown"

    def get_options(self, element: WebElement) -> list:
        radios = element.find_elements(By.XPATH, ".//input[@type='radio']")
        options = []
        for r in radios:
            label = r.find_element(By.XPATH, "./..")  # parent label
            options.append(label.text)
        return options

    def answer(self, element: WebElement, answer: str) -> bool:
        try:
            # find label containing answer
            labels = element.find_elements(By.TAG_NAME, "label")
            for lbl in labels:
                if answer.lower() in lbl.text.lower():
                    lbl.click()
                    return True
            # Try exact match with input value
            radios = element.find_elements(By.XPATH, ".//input[@type='radio']")
            for r in radios:
                if r.get_attribute("value") == answer:
                    r.click()
                    return True
            return False
        except Exception:
            return False

class TextHandler(QuestionHandler):
    def get_label(self, element: WebElement) -> str:
        try:
            label = element.find_element(By.TAG_NAME, "label")
            return label.text
        except:
            return "Unknown"

    def get_current_value(self, element: WebElement) -> str:
        inp = element.find_element(By.TAG_NAME, "input")
        return inp.get_attribute("value") or ""

    def answer(self, element: WebElement, answer: str) -> bool:
        try:
            inp = element.find_element(By.TAG_NAME, "input")
            from utils.helpers import clear_and_send_keys
            clear_and_send_keys(inp, answer)
            return True
        except:
            return False

class TextAreaHandler(QuestionHandler):
    def get_label(self, element: WebElement) -> str:
        try:
            label = element.find_element(By.TAG_NAME, "label")
            return label.text
        except:
            return "Unknown"

    def answer(self, element: WebElement, answer: str) -> bool:
        try:
            area = element.find_element(By.TAG_NAME, "textarea")
            from utils.helpers import clear_and_send_keys
            clear_and_send_keys(area, answer)
            return True
        except:
            return False

# Instantiate for convenience
SELECT_HANDLER = SelectHandler()
RADIO_HANDLER = RadioHandler()
TEXT_HANDLER = TextHandler()
TEXTAREA_HANDLER = TextAreaHandler()