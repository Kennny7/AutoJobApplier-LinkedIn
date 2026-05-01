"""
Job scraper: extract job cards from LinkedIn search results.
Inputs: WebDriver, ActionChains, applied job IDs set, blacklisted companies set.
Outputs: generator of (job_id, title, company, location, work_style, skip_reason) tuples.
"""

import re
import time
import logging
from typing import Generator, Optional, Set, Tuple, Dict, Any
from datetime import datetime, timedelta

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException

from utils.helpers import scroll_into_view, random_buffer
from core.state import state

logger = logging.getLogger("AutoApply.JobScraper")

def extract_job_id(element: WebElement) -> Optional[str]:
    """Return the job ID from a job card element."""
    return element.get_dom_attribute("data-occludable-job-id")

def get_job_main_details(job: WebElement, driver: WebDriver, actions: ActionChains,
                         applied_jobs: Set[str], blacklisted_companies: Set[str]) -> Tuple[str, str, str, str, str, Optional[str]]:
    """
    Extract basic job info and return (job_id, title, company, location, work_style, skip_reason).
    skip_reason is None if job should be processed, else string reason.
    """
    try:
        job_details_btn = job.find_element(By.TAG_NAME, "a")
        scroll_into_view(driver, job_details_btn, top=True)
    except NoSuchElementException:
        return ("", "", "", "", "", "No details link")

    job_id = extract_job_id(job) or ""
    title = job_details_btn.text.split("\n")[0].strip()
    
    # Subtitle contains company and location
    subtitle = job.find_element(By.CLASS_NAME, "artdeco-entity-lockup__subtitle").text
    # Format: "Company Name · Location"
    parts = subtitle.split(" · ")
    company = parts[0].strip() if len(parts) > 0 else "Unknown"
    location = parts[1].strip() if len(parts) > 1 else "Unknown"
    
    # Work style extraction
    work_style = ""
    if "(" in location and ")" in location:
        style_match = re.search(r'\((.*?)\)', location)
        if style_match:
            work_style = style_match.group(1)
            location = re.sub(r'\(.*?\)', '', location).strip()
    else:
        work_style = "On-site"  # default assumption
    
    # Check if already applied or blacklisted
    if job_id in applied_jobs:
        return (job_id, title, company, location, work_style, "Already applied")
    if company in blacklisted_companies:
        return (job_id, title, company, location, work_style, "Blacklisted company")
    
    # Check footer for "Applied" label
    try:
        footer = job.find_element(By.CLASS_NAME, "job-card-container__footer-job-state")
        if footer.text.strip().lower() == "applied":
            return (job_id, title, company, location, work_style, "Already applied (footer)")
    except NoSuchElementException:
        pass

    return (job_id, title, company, location, work_style, None)

def get_job_description(driver: WebDriver, wait: WebDriverWait) -> Tuple[str, Optional[int], Optional[str]]:
    """
    Read the job description from the expanded right pane.
    Returns (description_text, years_experience_required, skip_reason).
    skip_reason is None if okay.
    """
    try:
        desc_element = driver.find_element(By.CLASS_NAME, "jobs-box__html-content")
        description = desc_element.text
    except NoSuchElementException:
        return ("", None, "Description not found")
    
    # Check blacklist words in description
    bad_words = state.settings.get("blacklist", {}).get("bad_words_in_description", [])
    for word in bad_words:
        if word.lower() in description.lower():
            return (description, None, f"Bad word '{word}' in description")
    
    # Extract years of experience using regex
    years = None
    pattern = r'(\d+)[\+]?\s*(?:to\s*\d+)?\s*years?\s*(?:of\s*experience)?'
    matches = re.findall(pattern, description, re.IGNORECASE)
    if matches:
        years = max(int(m) for m in matches if int(m) <= 12)  # cap at 12
    return (description, years, None)

def calculate_date_posted(driver: WebDriver) -> datetime:
    """Parse the 'posted X ago' text and return a datetime object."""
    try:
        time_element = driver.find_element(By.XPATH, './/span[contains(text(), "ago")]')
        time_text = time_element.text.replace("Reposted", "").strip()
    except NoSuchElementException:
        return datetime.now()
    
    now = datetime.now()
    num = int(re.search(r'\d+', time_text).group(0))
    if "second" in time_text:
        return now - timedelta(seconds=num)
    elif "minute" in time_text:
        return now - timedelta(minutes=num)
    elif "hour" in time_text:
        return now - timedelta(hours=num)
    elif "day" in time_text:
        return now - timedelta(days=num)
    elif "week" in time_text:
        return now - timedelta(weeks=num)
    elif "month" in time_text:
        return now - timedelta(days=num*30)
    elif "year" in time_text:
        return now - timedelta(days=num*365)
    else:
        return now

def get_page_jobs(driver: WebDriver, wait: WebDriverWait) -> list:
    """Return list of job card WebElements on current page."""
    wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li[@data-occludable-job-id]")))
    return driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")

def go_to_next_page(driver: WebDriver, current_page: int) -> bool:
    """Try to click next page button. Returns True if advanced, False otherwise."""
    try:
        pagination = driver.find_element(By.XPATH, "//div[contains(@class,'jobs-search-pagination')]")
        next_btn = pagination.find_element(By.XPATH, f".//button[@aria-label='Page {current_page+1}']")
        next_btn.click()
        return True
    except NoSuchElementException:
        return False