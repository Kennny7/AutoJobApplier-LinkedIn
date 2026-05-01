"""
Global application state for tracking counts, applied jobs, and paused settings.
Thread-safe for future use but currently single-threaded.
"""

from typing import Set, Dict, Any
import logging

logger = logging.getLogger("AutoApply.State")

class AppState:
    """Singleton-like state that holds runtime counters and flags."""
    def __init__(self):
        self.easy_applied_count: int = 0
        self.external_jobs_count: int = 0
        self.failed_count: int = 0
        self.skip_count: int = 0
        self.total_runs: int = 0
        self.applied_job_ids: Set[str] = set()
        self.daily_limit_reached: bool = False
        self.settings: Dict[str, Any] = {}
        self.resume_path: str = ""
        self.pause_on_unknown: bool = False
        self.unknown_action: str = "pause"
        self.cycle_search: bool = False
        # Dynamic flags
        self.current_sort_by = ""
        self.current_date_posted = ""
        self.uploaded_resume_this_session = False

    def add_applied(self, job_id: str) -> None:
        self.applied_job_ids.add(job_id)
        self.easy_applied_count += 1

    @property
    def total_applied(self) -> int:
        return self.easy_applied_count + self.external_jobs_count

# Global instance
state = AppState()