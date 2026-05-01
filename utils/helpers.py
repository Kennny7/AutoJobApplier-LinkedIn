"""
Common Selenium helper functions.
Inputs: WebDriver, WebElement, ActionChains, etc.
Outputs: performed actions or retrieved elements.
"""

import time
import random
import logging
import os
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger("AutoApply.helpers")


def safe_wait(driver: WebDriver, timeout: float) -> WebDriverWait:
    """Return a WebDriverWait with given timeout."""
    return WebDriverWait(driver, timeout)


def click_element(actions: ActionChains, element: WebElement) -> None:
    """Click using ActionChains to avoid interception."""
    actions.move_to_element(element).click().perform()


def scroll_into_view(driver: WebDriver, element: WebElement, top: bool = False) -> None:
    """Scroll the element into view, optionally to the top."""
    # Currently set to always smooth; can be made configurable if needed
    behavior = "smooth"
    script = (
        'arguments[0].scrollIntoView({block: "center", behavior: "' + behavior + '"});'
    )
    if top:
        script = 'arguments[0].scrollIntoView(true);'
    driver.execute_script(script, element)


def safe_find_element(parent, by, value, timeout=5) -> WebElement:
    """Find element with wait, return WebElement or None."""
    try:
        return WebDriverWait(parent, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    except TimeoutException:
        return None


def wait_and_click(driver: WebDriver, xpath: str, timeout: float = 5) -> bool:
    """Wait for element by XPath, click it, return success."""
    try:
        elem = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", elem)
        time.sleep(0.3)
        elem.click()
        return True
    except Exception:
        return False


def send_keys_human_like(element: WebElement, text: str, min_delay=0.05, max_delay=0.15) -> None:
    """Type text with random delays to mimic human."""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(min_delay, max_delay))


def clear_and_send_keys(element: WebElement, text: str) -> None:
    """Clear an input field and send keys."""
    try:
        element.clear()
        element.send_keys(Keys.CONTROL + "a")
        element.send_keys(Keys.DELETE)
    except Exception:
        pass
    element.send_keys(text)


def random_buffer(base: float = 1.0, spread: float = 0.5) -> None:
    """Sleep for a random duration around base."""
    time.sleep(random.uniform(base - spread if base - spread > 0 else 0, base + spread))

def buffer(seconds: float = 1.0) -> None:
    """Sleep for the given number of seconds (used for consistent short pauses)."""
    time.sleep(seconds)

def safe_screenshot(driver: WebDriver, filename_prefix: str) -> str:
    """Take a screenshot and save to logs/screenshots directory."""
    path = Path("data/logs/screenshots") / f"{filename_prefix}_{int(time.time())}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        driver.save_screenshot(str(path))
        return str(path)
    except Exception:
        return ""