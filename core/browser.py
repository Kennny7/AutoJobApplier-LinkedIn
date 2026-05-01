"""
Browser session management. Creates a Chrome WebDriver with optional stealth and headless mode.
Inputs: Dictionary of settings (stealth, headless, etc).
Outputs: (WebDriver, ActionChains, WebDriverWait) tuple.
"""

import sys
import pathlib
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
try:
    import undetected_chromedriver as uc
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

from utils.exceptions import BrowserSessionError

logger = logging.getLogger("AutoApply.Browser")

def create_chrome_session(stealth: bool = False, headless: bool = False) -> tuple:
    """
    Initialise and return Chrome WebDriver, ActionChains, and WebDriverWait.
    
    Args:
        stealth: Use undetected_chromedriver if available.
        headless: Run browser headless.
    Returns:
        (driver, actions, wait)
    Raises:
        BrowserSessionError if session cannot be created.
    """
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Use temporary profile to avoid clashes
    temp_dir = pathlib.Path.home() / ".auto-job-apply-profile"
    temp_dir.mkdir(parents=True, exist_ok=True)
    options.add_argument(f"--user-data-dir={temp_dir}")

    if stealth and STEALTH_AVAILABLE:
        try:
            driver = uc.Chrome(options=options)
            logger.info("Launched undetected Chrome")
        except Exception as e:
            raise BrowserSessionError(f"Failed to start undetected Chrome: {e}")
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service as ChromeService

        service = ChromeService(ChromeDriverManager().install())
        try:
            driver = webdriver.Chrome(service=service, options=options)
            logger.info("Launched regular Chrome")
        except Exception as e:
            raise BrowserSessionError(f"Failed to start Chrome: {e}")

    # Remove webdriver property to avoid detection
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    driver.maximize_window()
    wait = WebDriverWait(driver, 10)
    actions = ActionChains(driver)
    return driver, actions, wait