#!/usr/bin/env python3
"""
Auto Job Applier - Main Entry Point.
Handles interactive CLI setup (Rich) and then starts the application loop.
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

from config.loader import load_config, save_user_data
from utils.logger import get_logger
from core.browser import create_chrome_session
from core.state import state

# --- New imports for application loop ---
from core.actions import click_element, random_buffer
from question_handling.matchers import KeywordMatcher, RegexMatcher, FuzzyMatcher, FakerFallbackMatcher
from question_handling.handlers import SELECT_HANDLER, RADIO_HANDLER, TEXT_HANDLER, TEXTAREA_HANDLER
from question_handling.router import QuestionRouter
from utils.csv_writer import create_applied_writer, create_failed_writer
from core.linkedin import login, apply_search_filters
from core.job_scraper import get_page_jobs, get_job_main_details, go_to_next_page, get_job_description
from core.easy_apply import EasyApplyProcess
from selenium.webdriver.common.by import By

# Initialise logger early
logger = get_logger("AutoApply")
console = Console()

def run_wizard(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Interactive first-time setup (or reconfiguration) using questionary.
    Returns updated user_data dictionary.
    """
    rprint(Panel.fit("[bold cyan]Welcome to Auto Job Applier 2026 Edition[/bold cyan]\nLet's configure your settings."))
    user = config.get("user", {})
    answers = config.get("answers", {})
    settings = config.get("settings", {})

    # 1. Resume path
    resume_path = questionary.path(
        "Path to your resume (PDF/DOCX):",
        default=settings.get("paths", {}).get("resume_path", "resume/my_resume.pdf"),
        validate=lambda p: Path(p).exists() or "File does not exist"
    ).ask()
    user["resume_path"] = resume_path

    # 2. Basic personal info
    user["first_name"] = questionary.text("First Name:", default=user.get("first_name", "")).ask()
    user["last_name"] = questionary.text("Last Name:", default=user.get("last_name", "")).ask()
    user["email"] = questionary.text("Email:", default=user.get("email", "")).ask()
    user["phone"] = questionary.text("Phone:", default=user.get("phone", "")).ask()
    user["city"] = questionary.text("City:", default=user.get("city", "")).ask()
    user["state"] = questionary.text("State:", default=user.get("state", "")).ask()
    user["zip"] = questionary.text("ZIP:", default=user.get("zip", "")).ask()
    user["country"] = questionary.text("Country:", default=user.get("country", "")).ask()
    user["linkedin"] = questionary.text("LinkedIn URL:", default=user.get("linkedin", "")).ask()
    user["website"] = questionary.text("Personal Website:", default=user.get("website", "")).ask()
    user["headline"] = questionary.text("LinkedIn Headline:", default=user.get("headline", "")).ask()
    user["summary"] = questionary.text("LinkedIn Summary:", default=user.get("summary", "")).ask()
    user["cover_letter"] = questionary.text("Default Cover Letter:", default=user.get("cover_letter", "")).ask()
    user["years_experience"] = questionary.text("Total Years of Experience:", default=user.get("years_experience", "5")).ask()
    user["recent_employer"] = questionary.text("Most Recent Employer:", default=user.get("recent_employer", "")).ask()
    user["desired_salary"] = questionary.text("Desired Salary (annual, numeric):", default=user.get("desired_salary", "100000")).ask()
    user["current_ctc"] = questionary.text("Current CTC (annual, numeric):", default=user.get("current_ctc", "80000")).ask()
    user["notice_period"] = questionary.text("Notice Period (days):", default=user.get("notice_period", "30")).ask()
    user["confidence_level"] = questionary.text("Confidence level (1-10):", default=user.get("confidence_level", "8")).ask()

    # 3. Behaviour
    state.settings = settings
    state.pause_on_unknown = questionary.confirm("Pause on unknown questions?").ask()
    unknown_actions = ["pause", "skip_job", "fill_placeholder", "fill_random"]
    state.unknown_action = questionary.select(
        "If unknown question and not pausing:",
        choices=unknown_actions
    ).ask()
    headless = questionary.confirm("Run browser headless?").ask()
    stealth = questionary.confirm("Use stealth mode (undetected chromedriver)?").ask()
    cycle = questionary.confirm("Cycle through sort/date filters after each run?").ask()
    max_apps = questionary.text("Max applications per session:", default="100").ask()

    # Save all into user_data
    user_data = {**user}
    user_data["headless"] = headless
    user_data["stealth"] = stealth
    user_data["cycle_search"] = cycle
    user_data["max_applications"] = int(max_apps)
    user_data["pause_on_unknown"] = state.pause_on_unknown
    user_data["unknown_action"] = state.unknown_action

    # Update state
    state.settings.update({
        "headless": headless,
        "stealth": stealth,
        "cycle_search": cycle,
        "max_applications": int(max_apps),
    })
    state.resume_path = resume_path
    state.current_sort_by = settings.get("search", {}).get("sort_by", "Most recent")
    state.current_date_posted = settings.get("search", {}).get("date_posted", "Past week")

    return user_data

def main():
    try:
        # 1. Load or create configuration
        config = load_config()
        user_data = config.get("user", {})
        if not user_data:   # No user data yet, run wizard
            user_data = run_wizard(config)
            save_user_data(user_data, "config/user_data.yaml")
            logger.info("User data saved. You can edit config/user_data.yaml to change later.")
        else:
            # Optionally allow reconfiguration
            if questionary.confirm("Do you want to reconfigure your settings?").ask():
                user_data = run_wizard(config)
                save_user_data(user_data, "config/user_data.yaml")

        # Update state with final settings
        state.settings = config.get("settings", {})
        state.resume_path = user_data.get("resume_path", "")
        state.pause_on_unknown = user_data.get("pause_on_unknown", True)
        state.unknown_action = user_data.get("unknown_action", "pause")
        max_apps = user_data.get("max_applications", 100)
        headless = user_data.get("headless", False)
        stealth = user_data.get("stealth", True)

        # 2. Launch browser
        driver, actions, wait = create_chrome_session(stealth=stealth, headless=headless)

        # 3. Main application loop (integrated from new logic)
        # Reload config to reflect any changes made by wizard / manual edits
        config = load_config()
        user_data = config.get("user", {})
        settings = config.get("settings", {})
        answers = config.get("answers", {})

        # Initialise state sets/counters if not already present
        state.applied_job_ids = getattr(state, "applied_job_ids", set())
        state.easy_applied_count = getattr(state, "easy_applied_count", 0)
        state.daily_limit_reached = getattr(state, "daily_limit_reached", False)

        # Prepare question router
        matchers = [
            KeywordMatcher(answers),
            RegexMatcher(),
            FuzzyMatcher(answers, threshold=75),
        ]
        # Optionally add faker matcher if fill_random is chosen
        if state.unknown_action == "fill_random":
            matchers.append(FakerFallbackMatcher())

        def user_pause_cb(label, qtype, context):
            return questionary.text(f"No answer for '{label}'. Enter answer or 'skip':").ask()

        router = QuestionRouter(
            matchers=matchers,
            handlers={
                "select": SELECT_HANDLER,
                "radio": RADIO_HANDLER,
                "text": TEXT_HANDLER,
                "textarea": TEXTAREA_HANDLER
            },
            unknown_action=state.unknown_action,
            user_pause_callback=user_pause_cb
        )

        # Load CSV writers
        applied_writer = create_applied_writer(settings.get("paths", {}).get("applied_csv", "data/applied_jobs.csv"))
        failed_writer = create_failed_writer(settings.get("paths", {}).get("failed_csv", "data/failed_jobs.csv"))

        # LinkedIn login
        login(driver, actions, wait,
              username=user_data.get("linkedin_email", ""),
              password=user_data.get("linkedin_password", ""))
        logger.info("Logged in LinkedIn.")

        # Main search loop
        search_terms = settings.get("search", {}).get("keywords", ["Python Developer"])
        location = settings.get("search", {}).get("location", "")
        filters = settings.get("search", {}).get("filters", {})

        # Initialize easy apply helper
        apply_process = EasyApplyProcess(driver, actions, wait, router,
                                         state.resume_path, applied_writer, failed_writer)

        total_runs = 0
        for term in search_terms:
            driver.get(f"https://www.linkedin.com/jobs/search/?keywords={term}")
            # Apply filters
            apply_search_filters(driver, actions, wait, location, filters)

            page = 1
            while True:
                logger.info(f"Processing page {page} of '{term}'")
                jobs = get_page_jobs(driver, wait)
                if not jobs:
                    logger.info("No jobs found on page.")
                    break

                for job in jobs:
                    job_id, title, company, loc, style, skip = get_job_main_details(
                        job, driver, actions, state.applied_job_ids, set()
                    )
                    if skip:
                        logger.info(f"Skipping {title} at {company}: {skip}")
                        continue

                    # Click job to expand details
                    try:
                        job_link_btn = job.find_element(By.TAG_NAME, "a")
                        click_element(actions, job_link_btn)
                        random_buffer(1)
                    except:
                        continue

                    # Get description
                    desc, years, skip_desc = get_job_description(driver, wait)
                    if skip_desc:
                        logger.info(f"Skip due to description: {skip_desc}")
                        continue

                    # Attempt Easy Apply
                    apply_process.apply_to_job(
                        job_id, title, company, loc, style,
                        f"https://www.linkedin.com/jobs/view/{job_id}",
                        desc
                    )

                    # Check limits
                    if state.easy_applied_count >= state.settings.get("max_applications", 100):
                        logger.info("Session application limit reached.")
                        driver.quit()
                        return

                    if state.daily_limit_reached:
                        break

                # Next page
                if not go_to_next_page(driver, page):
                    break
                page += 1
                random_buffer(2)

            if state.daily_limit_reached:
                break

        logger.info("All searches complete.")
        driver.quit()

    except Exception as e:
        logger.exception("Unhandled exception in main")
        rprint(f"[bold red]Fatal error:[/bold red] {e}")
        # Ensure driver is quit if it exists
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    sys.exit(main())