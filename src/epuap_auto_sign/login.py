"""Obsługa logowania do Profilu Zaufanego i kodów autoryzacyjnych SMS."""

from __future__ import annotations

import logging

from .browser import find_visible_input, wait_and_click
from .constants import STEP_TIMEOUT_MS

logger = logging.getLogger(__name__)

USERNAME_SELECTORS = [
    'input[name="username"]',
    'input[name="login"]',
    'input[id="username"]',
    'input[id="login"]',
    'input[type="text"]',
    'input[type="email"]',
]

PASSWORD_SELECTORS = [
    'input[name="password"]',
    'input[type="password"]',
    'input[id="password"]',
]

LOGIN_BUTTON_SELECTORS = [
    'button:has-text("Zaloguj się")',
    'button:has-text("Zaloguj")',
    'button[type="submit"]',
    'input[type="submit"]',
]

SMS_CODE_SELECTORS = [
    'input[name*="kod"]',
    'input[name*="code"]',
    'input[name*="otp"]',
    'input[id*="kod"]',
    'input[id*="code"]',
    'input[id*="otp"]',
    'input[type="text"]',
    'input[type="tel"]',
]

CONFIRM_BUTTON_SELECTORS = [
    'button:has-text("Potwierdź")',
    'button:has-text("potwierdź")',
    'button:has-text("Zatwierdź")',
    'button:has-text("Wyślij")',
    'button[type="submit"]',
    'input[type="submit"]',
]


def _fill_field(page, selectors: list[str], value: str, label: str) -> bool:
    """Znajduje pierwsze widoczne pole pasujące do selektorów i wypełnia je."""
    for selector in selectors:
        field = page.locator(selector).first
        try:
            if field.is_visible(timeout=2000):
                field.click()
                field.fill(value)
                logger.info("Wpisano %s (%s).", label, selector)
                return True
        except Exception:
            continue
    return False


def fill_login_form(page, credentials: dict[str, str]) -> bool:
    """Wypełnia formularz logowania do Profilu Zaufanego.

    Returns:
        True jeśli udało się wypełnić oba pola i kliknąć Zaloguj.
    """
    logger.info("Wypelniam formularz logowania...")
    page.wait_for_load_state("networkidle")

    username_filled = _fill_field(
        page, USERNAME_SELECTORS, credentials["username"], "nazwe uzytkownika"
    )
    if not username_filled:
        logger.warning("Nie udalo sie wpisac nazwy uzytkownika!")

    password_filled = _fill_field(page, PASSWORD_SELECTORS, credentials["password"], "haslo")
    if not password_filled:
        logger.warning("Nie udalo sie wpisac hasla!")

    if not (username_filled and password_filled):
        logger.info("Wypelnij formularz recznie w przegladarce.")
        return False

    wait_and_click(page, LOGIN_BUTTON_SELECTORS, "Zaloguj")
    return True


def handle_sms_code(
    page,
    label: str = "SMS",
    prompt_func=input,
    timeout_ms: int = STEP_TIMEOUT_MS,
) -> bool:
    """Wykrywa pole kodu autoryzacyjnego, pyta użytkownika i wypełnia pole.

    Args:
        page: Obiekt strony Playwright.
        label: Etykieta pokazywana w prompcie (np. "logowanie", "podpis").
        prompt_func: Funkcja do pobierania kodu od użytkownika
            (domyślnie input(), można podmienić w testach).
        timeout_ms: Czas oczekiwania na pole kodu.

    Returns:
        True jeśli kod został wprowadzony i zatwierdzony.
    """
    logger.info("Czekam na formularz kodu autoryzacyjnego (%s)...", label)
    code_field = find_visible_input(page, SMS_CODE_SELECTORS, timeout_ms)

    if not code_field:
        logger.info("Nie wykryto formularza kodu %s.", label)
        return False

    # DING! Powiadomienie dźwiękowe
    print("\a", end="", flush=True)
    sms_code = prompt_func(f"\n*** Wpisz kod autoryzacyjny ({label}): ").strip()

    if not sms_code:
        logger.warning("Nie podano kodu. Wpisz recznie w przegladarce.")
        return False

    code_field.click()
    code_field.fill(sms_code)
    logger.info("Wpisano kod autoryzacyjny (%s).", label)

    wait_and_click(page, CONFIRM_BUTTON_SELECTORS, "Potwierdź")
    return True
