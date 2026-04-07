"""Debug mode module - enables verbose logging for troubleshooting."""
import logging

debug_mode = False
logger = logging.getLogger("copilot_core")


def set_debug(enabled: bool) -> None:
    """Set debug mode globally."""
    global debug_mode
    debug_mode = enabled


def get_debug() -> bool:
    """Get current debug mode status."""
    return debug_mode
