"""
LinkedIn session management: login, filter setup.
Inputs: WebDriver, ActionChains, WebDriverWait, config (credentials, search criteria).
Outputs: None (modifies browser page directly).
"""

import time
import logging
from typing import Optional, Set, List

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from utils.exceptions import LoginFailed
from utils.helpers import safe_wait, click_element, scroll_into_view, random_buffer

logger = logging.getLogger("AutoApply.LinkedIn")

def is_logged_in(driver: WebDriver) -> bool:
    """Check if currently on LinkedIn feed or not showing login."""
    current_url = driver.current_url
    if "linkedin.com/feed" in current_url:
        return True
    try:
        driver.find_element(By.LINK_TEXT, "Sign in")
        return False
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.LINK_TEXT, "Join now")
        return False
    except NoSuchElementException:
        pass
    logger.debug("No login elements found, assuming logged in.")
    return True

def _wait_for_login(driver: WebDriver, timeout: int) -> bool:
    """Poll is_logged_in every 2 seconds until timeout. Returns True if logged in."""
    start = time.time()
    while time.time() - start < timeout:
        if is_logged_in(driver):
            return True
        time.sleep(2)
    return False

def login(driver: WebDriver, actions: ActionChains, wait: WebDriverWait,
          username: str, password: str) -> None:
    """
    Login to LinkedIn with automatic retry and manual fallback.
    
    Args:
        driver: Selenium WebDriver.
        actions: ActionChains.
        wait: WebDriverWait.
        username: LinkedIn email/phone.
        password: LinkedIn password.
    
    Raises:
        LoginFailed if all attempts fail.
    """
    driver.get("https://www.linkedin.com/login")
    
    # If already logged in, return immediately
    if is_logged_in(driver):
        logger.info("Already logged in LinkedIn.")
        return

    # If credentials not configured, go straight to manual login
    if not username or not password:
        logger.warning("No LinkedIn credentials provided. Manual login required.")
        import pyautogui
        pyautogui.alert(
            "Please log in to LinkedIn manually in the opened browser, then close this dialog.",
            "Manual Login", "Continue"
        )
        _wait_for_login(driver, timeout=120)
        return

    # Fill credentials
    try:
        username_field = wait.until(EC.element_to_be_clickable((By.ID, "username")))
    except TimeoutException:
        raise LoginFailed("Username field not found on login page.")
    
    username_field.clear()
    username_field.send_keys(username)
    time.sleep(0.5)
    
    password_field = driver.find_element(By.ID, "password")
    password_field.clear()
    password_field.send_keys(password)
    time.sleep(0.5)
    
    # Click submit
    driver.find_element(By.XPATH, '//button[@type="submit"]').click()
    
    # Wait patiently for login (possibly with 2FA)
    if _wait_for_login(driver, timeout=60):
        logger.info("Login successful.")
        return

    # If we get here, 2FA or another verification is likely needed
    logger.warning("Automatic login timed out – probably 2FA / verification step.")
    import pyautogui
    pyautogui.alert(
        "Please complete any security verification in the browser, then close this dialog.",
        "Verification", "Continue"
    )
    
    # Give the user extra time after dismissing the alert
    if _wait_for_login(driver, timeout=120):
        logger.info("Login completed after manual verification.")
        return

    raise LoginFailed("Login failed even after manual intervention.")

def apply_search_filters(driver: WebDriver, actions: ActionChains, wait: WebDriverWait,
                         search_location: str, filters: dict) -> None:
    """
    Navigate to the first search term's URL (job search) and apply filters.
    We'll be called per search term; location set once.
    
    Args:
        driver, actions, wait: Selenium tools.
        search_location: City, state, or zip.
        filters: dictionary of filter options (experience, job_type, etc.)
    """
    # Location
    if search_location:
        try:
            loc_input = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//input[@aria-label='City, state, or zip code']")
            ))
            # Select all existing text (e.g., default "India") to avoid concatenation
            actions.move_to_element(loc_input).click().perform()
            time.sleep(0.5)
            actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            loc_input.clear()
            loc_input.send_keys(search_location)
            time.sleep(2)
            actions.send_keys(Keys.ENTER).perform()
            logger.info(f"Search location set to {search_location}")
        except TimeoutException:
            logger.warning("Location input not found, skipping.")

    # Open All filters
    try:
        all_filters_btn = driver.find_element(By.XPATH, '//button[normalize-space()="All filters"]')
        click_element(actions, all_filters_btn)
        random_buffer(1)
    except Exception:
        logger.warning("All filters button not found.")
        return

    # Helper to click spans for lists
    def click_span_list(items: List[str]) -> None:
        if not items:
            return
        for item in items:
            xpath = f'.//span[normalize-space()="{item}"]'
            try:
                elem = driver.find_element(By.XPATH, xpath)
                scroll_into_view(driver, elem)
                elem.click()
                random_buffer(0.5)
            except NoSuchElementException:
                logger.debug(f"Filter option '{item}' not found")
                # Try to search and add (company filter)
                if filters.get("company"):
                    # Special handling: search for company and add
                    try:
                        add_company_btn = driver.find_element(By.XPATH, '//span[text()="Add a company"]')
                        click_element(actions, add_company_btn)
                        search_field = driver.find_element(By.XPATH, '//input[@placeholder="Add a company"]')
                        search_field.send_keys(item)
                        time.sleep(2)
                        actions.send_keys(Keys.ARROW_DOWN).perform()
                        actions.send_keys(Keys.ENTER).perform()
                        logger.info(f"Added company filter: {item}")
                    except Exception:
                        pass

    # Apply each filter group from config
    # We need to convert filter keys to the actual UI handling
    # The original code used specific functions; we'll implement a general approach
    filter_map = {
        "experience": "Experience Level",
        "job_type": "Job Type",
        "remote": "Remote",
        "under_10_applicants": "Under 10 applicants",
        "in_network": "In your network",
        "fair_chance": "Fair Chance Employer",
    }
    # Convert booleans to lists if needed
    for key, label in filter_map.items():
        value = filters.get(key)
        if isinstance(value, list):
            click_span_list(value)
        elif isinstance(value, bool) and value:
            click_span_list([label])
        elif isinstance(value, str) and value:
            click_span_list([value])

    # Show results
    try:
        show_results = driver.find_element(By.XPATH,
            '//button[contains(translate(@aria-label, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "apply current filters to show")]')
        click_element(actions, show_results)
        logger.info("Filters applied.")
    except NoSuchElementException:
        logger.warning("Show results button not found, filters may not be applied.")