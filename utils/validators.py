"""
Data validators and type converters.
All user inputs (from YAML or interactive wizard) should be cleaned through these
functions to avoid crashes from malformed strings.

Functions:
    extract_number     – pull the first integer from a human‑readable string
    safe_int           – return an int or a default, with logging
    clean_salary       – convert salary string (e.g. "10 LPA", "100000") to int (annual)
    clean_notice_period– convert notice period string to int (days)
    clean_experience   – convert years of experience string to int (years)
    clean_confidence   – convert confidence score to int (1‑10)

Each function is independent; new converters can be added following the same pattern.
"""

import re
import logging
from typing import Optional, Union

logger = logging.getLogger("AutoApply.Validators")

# ---------------------------------------------------------------------------
# Generic numeric extraction
# ---------------------------------------------------------------------------

def extract_number(text: str) -> Optional[int]:
    """
    Extract the first integer from a string.
    Handles formats like:
      "10 to 15 LPA"   -> 10
      "₹ 5,00,000"     -> 5 (first number, context needed for full parsing)
      "1+"             -> 1
      "45 days"        -> 45
    Returns None if no number is found.
    """
    # Remove common digit grouping separators (Indian and Western)
    cleaned = text.replace(",", "").replace(" ", "")
    match = re.search(r"(\d+)", cleaned)
    if match:
        return int(match.group(1))
    return None

def safe_int(value: Union[str, int, None], default: int, field_name: str = "unknown") -> int:
    """
    Convert a value to int safely.
    If value is already an int, return it.
    If it's a string, try extract_number first; if that fails, log and return default.
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        extracted = extract_number(value)
        if extracted is not None:
            logger.debug(f"Converted '{field_name}': '{value}' -> {extracted}")
            return extracted
    # Log a warning only if the value was not empty, to catch manual YAML errors
    if value:
        logger.warning(f"Could not parse '{field_name}' value '{value}', using default {default}")
    return default

# ---------------------------------------------------------------------------
# Domain‑specific cleaners (compose extract_number + logic)
# ---------------------------------------------------------------------------

def clean_salary(raw: Optional[str], default: int = 100000) -> int:
    """
    Convert a salary string to an integer representing annual salary.
    Accepted formats (case‑insensitive):
      - plain number: "100000", "1000000"
      - lakhs: "10 LPA", "10 lakh", "10L"
      - crores: "1 Cr", "1 Crore"
      - range: "10 to 15 LPA" -> takes first number as lakhs
    If only a raw number is given, we assume it is in lakhs if ≤ 100,
    otherwise treat as exact amount (to handle both "10" -> 10L and "100000" -> 100000).
    """
    if not raw:
        return default

    text = raw.strip().lower()
    # Check for crore
    if "cr" in text or "crore" in text:
        num = extract_number(text)
        if num is not None:
            return num * 10_000_000  # 1 Cr = 10,000,000
    # Check for lakh
    if "lakh" in text or "lpa" in text or text.endswith("l"):
        num = extract_number(text)
        if num is not None:
            return num * 100_000  # 1 Lakh = 100,000
    # Plain number: decide based on magnitude
    num = extract_number(text)
    if num is not None:
        if num <= 100:           # assume it's in lakhs
            return num * 100_000
        else:
            return num
    # fallback
    logger.warning(f"Salary '{raw}' not understood, using default {default}")
    return default

def clean_notice_period(raw: Optional[str], default: int = 30) -> int:
    """
    Convert a notice period string to days.
    Examples:
        "30 days"    -> 30
        "45 days"    -> 45
        "2 months"   -> 60
        "immediate"  -> 0
        "1 week"     -> 7
    """
    if not raw:
        return default
    text = raw.strip().lower()
    if "immediate" in text or "0" in text:
        return 0
    num = extract_number(text)
    if num is None:
        return default
    if "month" in text:
        return num * 30
    elif "week" in text:
        return num * 7
    else:  # assume days
        return num

def clean_experience(raw: Optional[str], default: int = 0) -> int:
    """
    Convert years of experience string to an integer.
    Examples:
        "5"              -> 5
        "3 years"        -> 3
        "1+ year"        -> 1
        "0-1"            -> 1 (upper bound)
    """
    if not raw:
        return default
    text = raw.strip().lower()
    # If there's a range like "0-1", take the maximum (right side)
    if "-" in text:
        parts = text.split("-")
        if len(parts) == 2:
            upper = extract_number(parts[1])
            if upper is not None:
                return upper
    # Otherwise use first number
    num = extract_number(text)
    return num if num is not None else default

def clean_confidence(raw: Optional[str], default: int = 8) -> int:
    """
    Convert confidence score to an integer between 1 and 10.
    Examples:
        "8"   -> 8
        "10"  -> 10
        "high"-> default
    """
    if not raw:
        return default
    num = extract_number(raw)
    if num is not None:
        return max(1, min(10, num))
    # Could map textual values, but for now just default
    logger.warning(f"Confidence '{raw}' not numeric, using default {default}")
    return default

# ---------------------------------------------------------------------------
# Additional cleaners can be added here (e.g., phone, email, url)
# ---------------------------------------------------------------------------
# def clean_phone(raw: str) -> str:
#     # Strip non‑digits, ensure minimum length, etc.
#     ...