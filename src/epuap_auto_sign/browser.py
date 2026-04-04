"""Pomocnicze funkcje do interakcji z przeglądarką Playwright."""

from __future__ import annotations

import logging

from .constants import POLL_INTERVAL_MS, STEP_TIMEOUT_MS

logger = logging.getLogger(__name__)


def wait_and_click(
    page,
    selectors: list[str],
    label: str,
    timeout_ms: int = STEP_TIMEOUT_MS,
    poll_interval_ms: int = POLL_INTERVAL_MS,
) -> bool:
    """Odpytuje stronę w pętli szukając przycisku pasującego do jednego z selektorów.

    Gdy znajdzie widoczny element - klika go. Strony SPA potrzebują czasu
    na wyrenderowanie elementów, dlatego używamy polling zamiast pojedynczej próby.

    Args:
        page: Obiekt strony Playwright.
        selectors: Lista selektorów CSS do sprawdzenia (w kolejności).
        label: Etykieta używana w logach.
        timeout_ms: Maksymalny czas oczekiwania.
        poll_interval_ms: Odstęp między próbami.

    Returns:
        True jeśli kliknięto element, False jeśli timeout.
    """
    logger.info("Szukam przycisku '%s'...", label)
    elapsed = 0
    while elapsed < timeout_ms:
        for selector in selectors:
            btn = page.locator(selector).first
            try:
                if btn.is_visible():
                    btn.click()
                    logger.info("Kliknieto '%s' (%s)", label, selector)
                    return True
            except Exception:
                continue
        page.wait_for_timeout(poll_interval_ms)
        elapsed += poll_interval_ms
        logger.debug("Czekam na '%s'... (%d ms)", label, elapsed)

    logger.info("Nie znaleziono '%s'. Kliknij recznie w przegladarce.", label)
    return False


def find_visible_input(page, selectors: list[str], timeout_ms: int = STEP_TIMEOUT_MS):
    """Odpytuje stronę szukając widocznego pola input.

    Returns:
        Locator znalezionego pola lub None.
    """
    elapsed = 0
    while elapsed < timeout_ms:
        for selector in selectors:
            field = page.locator(selector).first
            try:
                if field.is_visible():
                    return field
            except Exception:
                continue
        page.wait_for_timeout(POLL_INTERVAL_MS)
        elapsed += POLL_INTERVAL_MS
    return None
