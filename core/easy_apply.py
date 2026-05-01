"""
Easy Apply modal handler.
Inputs: WebDriver, ActionChains, WebDriverWait, resume path, question router, state.
Outputs: None (interacts with modal and logs).
"""

import time
import logging
from typing import Optional, Dict, Any

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
)

from utils.helpers import random_buffer, click_element, scroll_into_view
from question_handling.router import QuestionRouter
from core.state import state
from utils.csv_writer import CSVWriter

logger = logging.getLogger("AutoApply.EasyApply")

class EasyApplyProcess:
    def __init__(self, driver: WebDriver, actions: ActionChains, wait: WebDriverWait,
                 router: QuestionRouter, resume_path: str,
                 applied_writer: CSVWriter, failed_writer: CSVWriter):
        self.driver = driver
        self.actions = actions
        self.wait = wait
        self.router = router
        self.resume_path = resume_path
        self.applied_writer = applied_writer
        self.failed_writer = failed_writer

    def apply_to_job(self, job_id: str, title: str, company: str, location: str,
                     work_style: str, job_link: str, description: str) -> None:
        """
        Execute the Easy Apply flow for a given job.
        Returns when job is either applied, failed, or skipped.
        """
        try:
            # Click the Easy Apply button if found
            if not self._click_easy_apply():
                logger.warning(f"Easy Apply button not found for job {job_id}")
                state.external_jobs_count += 1
                # Could attempt external apply later
                return

            modal = self._get_modal()
            questions_answered = []
            resume_uploaded = False

            next_button_exists = True
            while next_button_exists:
                # Answer questions on current page
                questions = self._collect_questions(modal)
                for q in questions:
                    answer = self.router.answer_question(q, {"description": description})
                    if answer:
                        questions_answered.append(answer)
                    else:
                        logger.warning(f"Could not answer question: {q}")
                        # If pause, router might have handled; if skip_job, router will raise
                        pass

                # Upload resume if not done yet (once per session or per job)
                if not resume_uploaded and state.settings.get("behaviour", {}).get("resume_upload_once", True):
                    if not state.uploaded_resume_this_session:
                        self._upload_resume(modal)
                        state.uploaded_resume_this_session = True
                        resume_uploaded = True

                # Check for Review button
                try:
                    review_btn = modal.find_element(By.XPATH, './/span[normalize-space()="Review"]')
                    review_btn.click()
                    next_button_exists = False  # proceed to final steps
                except NoSuchElementException:
                    # Try Next button
                    try:
                        next_btn = modal.find_element(By.XPATH, './/button[contains(span, "Next")]')
                        next_btn.click()
                        random_buffer(1)
                    except NoSuchElementException:
                        # No more buttons, maybe it's final
                        next_button_exists = False

            # Final review and submit
            self._submit_application(modal)

            logger.info(f"Successfully applied to {title} at {company} (Job ID: {job_id})")
            state.add_applied(job_id)

            # Log to CSV
            self.applied_writer.write_row({
                "Job ID": job_id,
                "Title": title,
                "Company": company,
                "Location": location,
                "Work Style": work_style,
                "Description": description[:300],
                "Experience Required": "",  # can be pulled from description
                "HR Name": "Unknown",
                "HR Link": "Unknown",
                "Resume": self.resume_path if resume_uploaded else "Previous",
                "Reposted": False,
                "Date Posted": datetime.now().isoformat(),  # placeholder
                "Date Applied": datetime.now().isoformat(),
                "Job Link": job_link,
                "External Link": "Easy Applied",
                "Questions Found": str(questions_answered)
            })

        except Exception as e:
            logger.exception(f"Failed Easy Apply for job {job_id}: {e}")
            state.failed_count += 1
            # screenshot
            try:
                from utils.helpers import safe_screenshot
                safe_screenshot(self.driver, f"failed_{job_id}")
            except:
                pass
            self.failed_writer.write_row({
                "Job ID": job_id,
                "Job Link": job_link,
                "Resume Tried": self.resume_path,
                "Date listed": datetime.now().isoformat(),
                "Date Tried": datetime.now().isoformat(),
                "Reason": str(e),
                "Exception": repr(e),
                "Screenshot": f"failed_{job_id}.png"
            })
            self._discard_modal()

    def _click_easy_apply(self) -> bool:
        """Find and click Easy Apply button. Returns True if found."""
        # Try multiple methods
        xpaths = [
            ".//button[contains(@class,'jobs-apply-button') and contains(@aria-label, 'Easy')]",
            ".//a[contains(@href, 'openSDUIApplyFlow=true')]",
        ]
        for xp in xpaths:
            try:
                btn = self.driver.find_element(By.XPATH, xp)
                click_element(self.actions, btn)
                return True
            except NoSuchElementException:
                continue
        return False

    def _get_modal(self) -> WebElement:
        """Wait for and return the Easy Apply modal."""
        return self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "jobs-easy-apply-modal")))

    def _collect_questions(self, modal: WebElement):
        """Find all question elements on current modal page."""
        return modal.find_elements(By.XPATH, ".//div[@data-test-form-element]")

    def _upload_resume(self, modal: WebElement):
        """Upload resume file if file input present."""
        try:
            file_input = modal.find_element(By.NAME, "file")
            file_input.send_keys(self.resume_path)
            logger.info("Resume uploaded.")
        except NoSuchElementException:
            logger.debug("No file upload element found; resume likely already present.")

    def _submit_application(self, modal: WebElement):
        """Handle review step, follow company, submit."""
        # Wait for Review button and click
        try:
            review_btn = modal.find_element(By.XPATH, './/span[normalize-space()="Review"]')
            click_element(self.actions, review_btn)
        except NoSuchElementException:
            pass

        # Follow company checkbox
        if state.settings.get("behaviour", {}).get("follow_company", False):
            try:
                follow_checkbox = modal.find_element(By.XPATH, ".//input[@id='follow-company-checkbox']")
                if not follow_checkbox.is_selected():
                    follow_checkbox.click()
            except:
                pass

        # Submit
        try:
            submit_btn = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, './/span[normalize-space()="Submit application"]')
            ))
            click_element(self.actions, submit_btn)
            time.sleep(1)
            # Done button
            try:
                done_btn = self.driver.find_element(By.XPATH, './/span[normalize-space()="Done"]')
                done_btn.click()
            except:
                pass
        except TimeoutException:
            logger.warning("Submit button not found; application may have failed.")

    def _discard_modal(self):
        """Close the modal by pressing Escape or clicking discard."""
        try:
            self.actions.send_keys(Keys.ESCAPE).perform()
        except:
            pass