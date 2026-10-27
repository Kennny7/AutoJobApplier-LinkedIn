"""
Interactive and non-interactive Rich CLI for AutoJobApplier & Email Dispatcher.
No emojis used.
"""

import os
import sys
import asyncio
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.box import ROUNDED

console = Console(force_terminal=True, highlight=False)

def print_banner(app_name: str = "AutoJobApplier & Mailer") -> None:
    banner_text = (
        "============================================================\n"
        f"   {app_name.upper()}\n"
        "   Automated LinkedIn Easy Apply, Resume Tailoring & Email Outreach\n"
        "============================================================"
    )
    console.print(Panel(banner_text, box=ROUNDED, border_style="cyan"))

def print_job_table(jobs: list) -> None:
    table = Table(title="Discovered Job Openings", box=ROUNDED, border_style="blue")
    table.add_column("No.", justify="right", style="cyan")
    table.add_column("Job Title", style="bold white")
    table.add_column("Company", style="yellow")
    table.add_column("Location", style="green")
    table.add_column("Apply Channel", style="magenta")

    for idx, j in enumerate(jobs, 1):
        email_or_url = j.get("apply_email") or j.get("url") or "Portal"
        table.add_row(
            str(idx),
            j.get("title", "Unknown"),
            j.get("company", "Unknown"),
            j.get("location", "Remote"),
            email_or_url[:35],
        )
    console.print(table)

def print_status(message: str, level: str = "info") -> None:
    colors = {"info": "cyan", "success": "green", "warning": "yellow", "error": "red"}
    c = colors.get(level, "white")
    console.print(f"[{c}][{level.upper()}][/{c}] {message}")
