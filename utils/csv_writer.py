"""
Thread‑safe CSV writers for applied and failed jobs.
Inputs: file paths, field names.
Outputs: writer objects for appending rows.
"""

import csv
import os
import threading
from typing import List, Dict, Any

lock = threading.Lock()

class CSVWriter:
    def __init__(self, filepath: str, fieldnames: List[str]):
        self.filepath = filepath
        self.fieldnames = fieldnames
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self._init_file()

    def _init_file(self):
        with lock:
            if not os.path.isfile(self.filepath):
                with open(self.filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                    writer.writeheader()

    def write_row(self, row_dict: Dict[str, Any]):
        try:
            with lock:
                with open(self.filepath, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                    writer.writerow(row_dict)
        except Exception as e:
            logging.getLogger("AutoApply.CSV").exception(f"Failed to write csv: {e}")

# Predefined writers
def create_applied_writer(path: str) -> CSVWriter:
    fields = [
        "Job ID", "Title", "Company", "Location", "Work Style",
        "Description", "Experience Required", "HR Name", "HR Link",
        "Resume", "Reposted", "Date Posted", "Date Applied", "Job Link",
        "External Link", "Questions Found"
    ]
    return CSVWriter(path, fields)

def create_failed_writer(path: str) -> CSVWriter:
    fields = [
        "Job ID", "Job Link", "Resume Tried", "Date listed",
        "Date Tried", "Reason", "Exception", "Screenshot"
    ]
    return CSVWriter(path, fields)