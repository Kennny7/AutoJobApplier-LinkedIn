# Auto_Job_Applier\core\easy_apply.py
"""
Easy Apply modal handler.
Inputs: WebDriver, ActionChains, WebDriverWait, resume path, question router, state.
Outputs: None (interacts with modal and logs).
"""

import time
import logging
from typing import Optional, Dict, Any, Set, Tuple, Union

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
)

from utils.helpers import (
    random_buffer, 
    click_element, 
    scroll_into_view, 
    buffer
)

from utils.validators import (
    clean_salary,
    clean_notice_period,
    clean_experience,
    safe_int,
    extract_number
)

from question_handling.router import QuestionRouter
from core.state import state
from utils.csv_writer import CSVWriter

logger = logging.getLogger("AutoApply.EasyApply")

class EasyApplyProcess:
    def __init__(self, driver: WebDriver, actions: ActionChains, wait: WebDriverWait,
                 router: QuestionRouter, resume_path: str,
                 applied_writer: CSVWriter, failed_writer: CSVWriter,
                 user_data: Dict[str, Any] = None):
        self.driver = driver
        self.actions = actions
        self.wait = wait
        self.router = router
        self.resume_path = resume_path
        self.applied_writer = applied_writer
        self.failed_writer = failed_writer

        # self.user_data = user_data or {}
        # # Pre‑compute frequently used strings
        # self.full_name = " ".join(filter(None, [
        #     self.user_data.get("first_name", ""),
        #     self.user_data.get("middle_name", ""),
        #     self.user_data.get("last_name", "")
        # ])).strip()
        # self.years_experience = str(self.user_data.get("years_experience", "5"))
        # self.phone_number = self.user_data.get("phone", "")
        # # salary variants
        # desired_salary = int(self.user_data.get("desired_salary", 100000))
        # current_ctc = int(self.user_data.get("current_ctc", 80000))
        # self.desired_salary_str = str(desired_salary)
        # self.desired_salary_lakhs = str(round(desired_salary / 100000, 2))
        # self.desired_salary_monthly = str(round(desired_salary/12, 2))
        # self.current_ctc_str = str(current_ctc)
        # self.current_ctc_lakhs = str(round(current_ctc / 100000, 2))
        # self.current_ctc_monthly = str(round(current_ctc/12, 2))
        # notice_days = int(self.user_data.get("notice_period", 30))
        # self.notice_period_str = str(notice_days)
        # self.notice_period_months = str(notice_days//30)
        # self.notice_period_weeks = str(notice_days//7)

        self.user_data = user_data or {}
        # Pre‑compute frequently used strings
        self.full_name = " ".join(filter(None, [
            self.user_data.get("first_name", ""),
            self.user_data.get("middle_name", ""),
            self.user_data.get("last_name", "")
        ])).strip()

        # Years of experience – use clean_experience to get integer, store string version for forms
        exp_int = clean_experience(self.user_data.get("years_experience"), default=0)
        self.years_experience = str(exp_int) if exp_int > 0 else "5"

        self.phone_number = self.user_data.get("phone", "")

        # Salary variants – safe integer conversion with domain‑specific cleaning
        desired_salary = clean_salary(self.user_data.get("desired_salary"), default=120000)
        current_ctc = clean_salary(self.user_data.get("current_ctc"), default=80000)

        self.desired_salary_str = str(desired_salary)
        self.desired_salary_lakhs = str(round(desired_salary / 120000, 2))
        self.desired_salary_monthly = str(round(desired_salary / 12, 2))

        self.current_ctc_str = str(current_ctc)
        self.current_ctc_lakhs = str(round(current_ctc / 120000, 2))
        self.current_ctc_monthly = str(round(current_ctc / 12, 2))

        # Notice period – clean as days integer, then derive other formats
        notice_days = clean_notice_period(self.user_data.get("notice_period"), default=30)
        self.notice_period_str = str(notice_days)
        self.notice_period_months = str(notice_days // 30)
        self.notice_period_weeks = str(notice_days // 7)

    def apply_to_job(self, job_id: str, title: str, company: str, location: str,
                     work_style: str, job_link: str, description: str) -> None:
        """
        Execute the Easy Apply flow for a given job.
        Uses the same robust multi‑page “Next” / “Review” loop as the reference project.
        """
        try:
            # 1. Click Easy Apply button
            if not self._click_easy_apply():
                logger.warning(f"Easy Apply button not found for job {job_id}")
                state.external_jobs_count += 1
                return

            # 2. Get modal
            modal = self._get_modal()

            # 3. Main question‑answering loop
            questions_answered: Set[Tuple[str, str, str, str]] = set()
            resume_uploaded = False
            next_counter = 0

            while True:
                next_counter += 1
                if next_counter > 15:
                    logger.error("Too many Next pages – something is stuck.")
                    break

                # Answer all questions on the current modal page
                self._answer_questions_on_page(modal, questions_answered, location, description)

                # Upload resume if not yet done (once per job)
                if not resume_uploaded and state.settings.get("behaviour", {}).get("resume_upload_once", True):
                    if not getattr(state, "uploaded_resume_this_session", False):
                        self._upload_resume(modal)
                        state.uploaded_resume_this_session = True
                        resume_uploaded = True

                # Look for Review / Next / Submit
                found_review = self._try_click_review(modal)
                if found_review:
                    break  # Review button clicked, exit loop to finalise

                # Try to click Next
                if not self._try_click_next(modal):
                    # No Next button – maybe final page without Review? check for Submit directly
                    if self._try_click_submit(modal):
                        break  # Submitted successfully
                    # If still nothing, break to avoid infinite loop
                    logger.debug("No Next/Review/Submit button found, exiting modal loop.")
                    break

                # Short wait for next page to load
                random_buffer(1)

            # 4. Final submission steps (if not already submitted)
            self._finalise_application(job_id, title, company, location, work_style, job_link, description, questions_answered)

        except Exception as e:
            logger.exception(f"Failed Easy Apply for job {job_id}: {e}")
            state.failed_count += 1
            # Screenshot for debugging
            try:
                from utils.helpers import safe_screenshot
                safe_screenshot(self.driver, f"failed_{job_id}")
            except:
                pass
            self.failed_writer.write_row({
                "Job ID": job_id,
                "Job Link": job_link,
                "Resume Tried": self.resume_path,
                "Date listed": "",  # not available at this point
                "Date Tried": time.strftime("%Y-%m-%d %H:%M:%S"),
                "Reason": str(e),
                "Exception": repr(e),
                "Screenshot": f"failed_{job_id}.png"
            })
            self._discard_modal()

    # ------------------------------------------------------------------
    # Existing (unchanged) helper methods
    # ------------------------------------------------------------------
    def _click_easy_apply(self) -> bool:
        """Find and click Easy Apply button. Returns True if found."""
        xpaths = [
            ".//button[contains(@class,'jobs-apply-button') and contains(@aria-label, 'Easy')]",
            ".//a[contains(@href, 'openSDUIApplyFlow=true')]",
        ]
        for xp in xpaths:
            try:
                btn = self.driver.find_element(By.XPATH, xp)
                click_element(self.actions, btn)
                random_buffer(1)
                return True
            except NoSuchElementException:
                continue
        return False

    def _get_modal(self) -> WebElement:
        """Wait for and return the Easy Apply modal."""
        return self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "jobs-easy-apply-modal")))

    def _upload_resume(self, modal: WebElement) -> None:
        """Upload resume file if file input present."""
        try:
            file_input = modal.find_element(By.NAME, "file")
            file_input.send_keys(self.resume_path)
            logger.info("Resume uploaded.")
        except NoSuchElementException:
            logger.debug("No file upload element found; resume likely already present.")

    def _discard_modal(self) -> None:
        """Close the modal by pressing Escape or clicking discard."""
        try:
            self.actions.send_keys(Keys.ESCAPE).perform()
        except:
            pass

    # ------------------------------------------------------------------
    # New / improved methods for robust multi‑page handling
    # ------------------------------------------------------------------
    def _answer_questions_on_page(self, modal: WebElement,
                                  answered_set: Set[Tuple[str, str, str, str]],
                                  work_location: str, job_description: str) -> None:
        """
        Answer all questions present on the current modal page.
        Uses a combination of the router and fallback direct matching.
        """
        question_elements = modal.find_elements(By.XPATH, ".//div[@data-test-form-element]")
        for q_el in question_elements:
            # Detect question type
            select_el = self._safe_find(q_el, ".//select")
            if select_el:
                self._answer_select(select_el, answered_set, q_el)
                continue
            radio_fs = self._safe_find(q_el, './/fieldset[@data-test-form-builder-radio-button-form-component="true"]')
            if radio_fs:
                self._answer_radio(radio_fs, answered_set, q_el)
                continue
            text_input = self._safe_find(q_el, ".//input[@type='text']")
            if text_input:
                self._answer_text(text_input, answered_set, q_el, work_location)
                continue
            textarea = self._safe_find(q_el, ".//textarea")
            if textarea:
                self._answer_textarea(textarea, answered_set, q_el)
                continue
            checkbox = self._safe_find(q_el, ".//input[@type='checkbox']")
            if checkbox:
                self._answer_checkbox(checkbox, answered_set, q_el)
                continue
        # Click today's date if present (common footer)
        try:
            today_btn = modal.find_element(By.XPATH, "//button[contains(@aria-label, 'This is today')]")
            today_btn.click()
        except:
            pass

    def _safe_find(self, parent, xpath):
        """Return element if it exists, else None."""
        try:
            return parent.find_element(By.XPATH, xpath)
        except NoSuchElementException:
            return None

    # Answering individual question types
    def _answer_select(self, select_el, answered_set, container):
        """Answer a <select> question."""
        try:
            label_el = container.find_element(By.TAG_NAME, "label")
            label = label_el.find_element(By.TAG_NAME, "span").text
        except:
            label = "Unknown"
        label_lower = label.lower()
        select = Select(select_el)
        selected = select.first_selected_option.text
        answer = self._resolve_select_answer(label_lower, selected)

        if answer and selected != answer:
            # Try exact match, then fuzzy
            try:
                select.select_by_visible_text(answer)
            except NoSuchElementException:
                options_text = [o.text for o in select.options]
                # Fuzzy matching (bidirectional)
                found = False
                for opt in options_text:
                    if answer.lower() in opt.lower() or opt.lower() in answer.lower():
                        select.select_by_visible_text(opt)
                        answer = opt
                        found = True
                        break
                if not found:
                    logger.warning(f"Could not find answer '{answer}' for select '{label}'. Selecting random.")
                    if len(select.options) > 1:
                        select.select_by_index(1)  # skip first placeholder
                        answer = select.first_selected_option.text
            answered_set.add((label, answer, "select", selected))
            buffer(0.3)

    def _resolve_select_answer(self, label, current_val):
        """Return the appropriate answer string for a select question."""
        # Default to current value if already answered (and we don't overwrite)
        if current_val and current_val != "Select an option":
            # Optionally overwrite? For now keep existing
            return current_val
        if "email" in label or "phone" in label:
            return current_val  # don't change
        if "gender" in label or "sex" in label:
            return self.user_data.get("gender", "Decline")
        if "disability" in label:
            return self.user_data.get("disability_status", "Decline")
        if "proficiency" in label:
            return "Professional"
        # Location
        if any(w in label for w in ["location", "city", "state", "country"]):
            if "country" in label:
                return self.user_data.get("country", "")
            if "state" in label:
                return self.user_data.get("state", "")
            if "city" in label:
                return self.user_data.get("city", "")
            return self.user_data.get("city", "")
        # Default to "Yes"
        return "Yes"

    def _answer_radio(self, fieldset, answered_set, container):
        """Answer a radio group."""
        try:
            label_el = fieldset.find_element(By.XPATH, './/span[@data-test-form-builder-radio-button-form-component__title]')
            label = label_el.text
        except:
            # try visually-hidden
            try:
                hidden = fieldset.find_element(By.CLASS_NAME, "visually-hidden")
                label = hidden.text
            except:
                label = "Unknown"
        label_lower = label.lower()
        inputs = fieldset.find_elements(By.TAG_NAME, "input")
        selected_label = None
        selected_value = None
        # Find currently selected
        for inp in inputs:
            id_ = inp.get_attribute("id")
            associated_label = self._safe_find(fieldset, f'.//label[@for="{id_}"]')
            txt = associated_label.text if associated_label else "Unknown"
            if inp.is_selected():
                selected_value = inp.get_attribute("value")
                selected_label = txt
                break
        if selected_value:  # already answered and we don't overwrite
            answered_set.add((label, selected_label, "radio", selected_label))
            return
        # Determine answer
        answer_text = self._resolve_radio_answer(label_lower)
        found_el = None
        for inp in inputs:
            id_ = inp.get_attribute("id")
            associated_label = self._safe_find(fieldset, f'.//label[@for="{id_}"]')
            txt = associated_label.text if associated_label else ""
            if answer_text.lower() in txt.lower() or (answer_text == "Decline" and any(
                phrase in txt.lower() for phrase in ["decline", "not wish", "don't wish", "prefer not"]
            )):
                found_el = associated_label
                answer_text = txt
                break
        if not found_el:
            # try to click the first option as fallback
            if inputs:
                found_el = self._safe_find(fieldset, f'.//label[@for="{inputs[0].get_attribute("id")}"]')
                answer_text = "Decline (fallback)"
            else:
                return
        try:
            self.actions.move_to_element(found_el).click().perform()
            buffer(0.3)
        except:
            pass
        answered_set.add((label, answer_text, "radio", selected_label if selected_label else "None"))

    def _resolve_radio_answer(self, label):
        if "citizenship" in label or "employment eligibility" in label:
            return self.user_data.get("us_citizenship", "Decline")
        if "veteran" in label or "protected" in label:
            return self.user_data.get("veteran_status", "Decline")
        if "disability" in label:
            return self.user_data.get("disability_status", "Decline")
        # default "Yes"
        return "Yes"

    def _answer_text(self, input_el, answered_set, container, work_location):
        """Answer a text input."""
        try:
            label_el = container.find_element(By.XPATH, ".//label[@for]")
            label = label_el.text
        except:
            try:
                hidden = label_el.find_element(By.CLASS_NAME, "visually-hidden")
                label = hidden.text
            except:
                label = "Unknown"
        label_lower = label.lower()
        current_val = input_el.get_attribute("value")
        if current_val:
            answered_set.add((label, current_val, "text", current_val))
            return
        answer = self._resolve_text_answer(label_lower, work_location)
        if answer:
            input_el.clear()
            input_el.send_keys(answer)
            # If it's an address field, may need to select from dropdown
            if any(w in label_lower for w in ["city", "location", "address"]):
                time.sleep(2)
                self.actions.send_keys(Keys.ARROW_DOWN).send_keys(Keys.ENTER).perform()
            answered_set.add((label, answer, "text", current_val))
        else:
            # Fallback: use router or leave empty
            question = {"label": label, "type": "text"}
            ans = self.router.answer_question(question, {"description": job_description})
            if ans:
                input_el.clear()
                input_el.send_keys(ans)
                answered_set.add((label, ans, "text", current_val))
        buffer(0.3)

    def _resolve_text_answer(self, label, work_location):
        """Return answer for text input based on label."""
        if "first name" in label and "last" not in label:
            return self.user_data.get("first_name", "")
        if "last name" in label and "first" not in label:
            return self.user_data.get("last_name", "")
        if "full name" in label:
            return self.full_name
        if ("name" in label) and not any(x in label for x in ["first", "last", "middle"]):
            return self.full_name
        if "email" in label:
            return self.user_data.get("email", "")
        if "phone" in label or "mobile" in label:
            return self.phone_number
        if "years" in label or "experience" in label:
            return self.years_experience
        if "salary" in label or "compensation" in label or "ctc" in label or "pay" in label:
            if "current" in label or "present" in label:
                if "month" in label:
                    return self.current_ctc_monthly
                if "lakh" in label:
                    return self.current_ctc_lakhs
                return self.current_ctc_str
            else:
                if "month" in label:
                    return self.desired_salary_monthly
                if "lakh" in label:
                    return self.desired_salary_lakhs
                return self.desired_salary_str
        if "notice" in label:
            if "month" in label:
                return self.notice_period_months
            if "week" in label:
                return self.notice_period_weeks
            return self.notice_period_str
        if "street" in label:
            return self.user_data.get("street", "")
        if "city" in label or "location" in label or "address" in label:
            return self.user_data.get("city", "") or work_location
        if "zip" in label or "postal" in label or "code" in label:
            return self.user_data.get("zip", "")
        if "state" in label or "province" in label:
            return self.user_data.get("state", "")
        if "country" in label:
            return self.user_data.get("country", "")
        if "linkedin" in label:
            return self.user_data.get("linkedin", "")
        if "website" in label or "blog" in label or "portfolio" in label:
            return self.user_data.get("website", "")
        if "headline" in label:
            return self.user_data.get("headline", "")
        if "summary" in label:
            return self.user_data.get("summary", "")
        if "cover" in label:
            return self.user_data.get("cover_letter", "")
        if "employer" in label:
            return self.user_data.get("recent_employer", "")
        if "confidence" in label or "scale of 1-10" in label:
            return self.user_data.get("confidence_level", "8")
        if "hear" in label or "come across" in label:
            return "https://github.com/GodsScion/Auto_job_applier_linkedIn"
        return None  # will be handled by router fallback

    def _answer_textarea(self, textarea_el, answered_set, container):
        """Answer a textarea."""
        try:
            label_el = container.find_element(By.XPATH, ".//label[@for]")
            label = label_el.text
        except:
            label = "Unknown"
        label_lower = label.lower()
        current_val = textarea_el.get_attribute("value")
        if current_val:
            answered_set.add((label, current_val, "textarea", current_val))
            return
        answer = None
        if "summary" in label_lower:
            answer = self.user_data.get("summary", "")
        elif "cover" in label_lower:
            answer = self.user_data.get("cover_letter", "")
        if answer:
            textarea_el.clear()
            textarea_el.send_keys(answer)
            answered_set.add((label, answer, "textarea", current_val))
            buffer(0.3)
        else:
            # fallback router
            question = {"label": label, "type": "textarea"}
            ans = self.router.answer_question(question, {"description": job_description})
            if ans:
                textarea_el.clear()
                textarea_el.send_keys(ans)
                answered_set.add((label, ans, "textarea", current_val))

    def _answer_checkbox(self, checkbox_el, answered_set, container):
        """Toggle checkbox if not already selected."""
        if not checkbox_el.is_selected():
            try:
                self.actions.move_to_element(checkbox_el).click().perform()
            except:
                pass
        # label for logging
        try:
            label_el = container.find_element(By.XPATH, ".//label[@for]")
            label = label_el.text
        except:
            label = "Unknown"
        answered_set.add((f"checkbox: {label}", str(checkbox_el.is_selected()), "checkbox", ""))

    def _try_click_review(self, modal) -> bool:
        """Look for 'Review' button and click it. Return True if found."""
        try:
            review_btn = modal.find_element(By.XPATH, './/span[normalize-space()="Review"]')
            click_element(self.actions, review_btn)
            random_buffer(0.5)
            return True
        except NoSuchElementException:
            return False

    def _try_click_next(self, modal) -> bool:
        """Look for 'Next' button and click it. Return True if found."""
        try:
            next_btn = modal.find_element(By.XPATH, './/button[contains(span, "Next")]')
            click_element(self.actions, next_btn)
            random_buffer(1)
            return True
        except NoSuchElementException:
            return False

    def _try_click_submit(self, modal) -> bool:
        """Look for 'Submit application' and click. Return True if clicked."""
        try:
            submit_btn = modal.find_element(By.XPATH, './/span[normalize-space()="Submit application"]')
            click_element(self.actions, submit_btn)
            time.sleep(1)
            return True
        except NoSuchElementException:
            return False

    def _finalise_application(self, job_id, title, company, location, work_style,
                              job_link, description, questions_answered):
        """
        Click Follow company (if desired), Submit, and Done.
        Also log success and write applied CSV.
        """
        modal = self._get_modal()  # modal still present
        # Follow company checkbox
        if self.user_data.get("follow_companies", False):
            try:
                follow = modal.find_element(By.XPATH, ".//input[@id='follow-company-checkbox']")
                if not follow.is_selected():
                    follow.click()
                    logger.debug("Follow company checkbox enabled.")
            except:
                pass

        # Submit (if not already clicked)
        submitted = False
        try:
            submit_span = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, './/span[normalize-space()="Submit application"]'))
            )
            click_element(self.actions, submit_span)
            submitted = True
            time.sleep(1)
        except TimeoutException:
            logger.warning("Submit button not found, may have already submitted.")
            submitted = True  # assume success if no error

        if submitted:
            # Click Done
            try:
                done_btn = self.driver.find_element(By.XPATH, './/span[normalize-space()="Done"]')
                done_btn.click()
            except:
                pass

            logger.info(f"Successfully applied to {title} at {company} (Job ID: {job_id})")
            state.add_applied(job_id)

            # Write to applied CSV
            self.applied_writer.write_row({
                "Job ID": job_id,
                "Title": title,
                "Company": company,
                "Location": location,
                "Work Style": work_style,
                "Description": description[:300],
                "Experience Required": "",
                "HR Name": "Unknown",
                "HR Link": "Unknown",
                "Resume": self.resume_path if getattr(state, "uploaded_resume_this_session", False) else "Previous",
                "Reposted": False,
                "Date Posted": "",
                "Date Applied": time.strftime("%Y-%m-%d %H:%M:%S"),
                "Job Link": job_link,
                "External Link": "Easy Applied",
                "Questions Found": str(questions_answered)
            })
        else:
            raise Exception("Unable to submit application.")