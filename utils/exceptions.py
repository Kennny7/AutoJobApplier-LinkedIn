"""Custom exceptions for the Auto Job Applier. 
All exceptions are handled at the top level to either skip the job or abort gracefully."""

class AutoApplyError(Exception):
    """Base exception for the application."""

class LoginFailed(AutoApplyError):
    """Raised when login to LinkedIn fails after retries."""

class DailyLimitReached(AutoApplyError):
    """Raised when LinkedIn reports daily Easy Apply limit exceeded."""

class ModalClosed(AutoApplyError):
    """Raised when the Easy Apply modal disappears unexpectedly."""

class UnanswerableQuestion(AutoApplyError):
    """Raised when a question cannot be answered and user chose to skip/pause."""

class BrowserSessionError(AutoApplyError):
    """Raised when the browser session becomes invalid."""

class ConfigError(AutoApplyError):
    """Raised for configuration issues."""