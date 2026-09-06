"""Google Email Checker - Modular package."""

from .client import CamofoxClient
from .engine import check_account, do_logout, beep_success
from .loaders import load_accounts, generate_email
from .reporter import generate_report, generate_html_report
from .config import (
    DEFAULT_PASSWORD,
    EMAIL_DOMAIN,
    LOGIN_URL,
    LOGOUT_URL,
    DEFAULT_SERVER_URL,
    DELAY_BETWEEN_ACCOUNTS,
)

__all__ = [
    "CamofoxClient",
    "check_account",
    "do_logout",
    "beep_success",
    "load_accounts",
    "generate_email",
    "generate_report",
    "generate_html_report",
    "DEFAULT_PASSWORD",
    "EMAIL_DOMAIN",
    "LOGIN_URL",
    "LOGOUT_URL",
    "DEFAULT_SERVER_URL",
    "DELAY_BETWEEN_ACCOUNTS",
]
