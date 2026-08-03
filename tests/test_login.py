"""Testy modulu login - obsluga kodu SMS.

Fake'i modeluja kluczowa wlasciwosc Playwright: Locator jest "zywy",
tzn. selektor jest rozwiazywany od nowa przy kazdej akcji, na aktualnym
stanie strony. Widocznosc elementu to uproszczenie: strona trzyma zbior
selektorow, ktore "pasuja do widocznego elementu" w danej chwili.
"""

from __future__ import annotations

import pytest

from epuap_auto_sign.login import handle_sms_code

LOGIN_PAGE = frozenset(
    {
        'input[type="text"]',  # pole username
        'input[type="password"]',
    }
)

SMS_PAGE = frozenset(
    {
        'input[id*="kod"]',
        'button:has-text("Potwierdź")',
    }
)


class FakeTimeoutError(Exception):
    """Odpowiednik playwright TimeoutError przy akcji na niewidocznym elemencie."""


class FakeLocator:
    """Imituje Locator Playwright: rozwiazuje selektor przy kazdej akcji."""

    def __init__(self, page: FakePage, selector: str):
        self.page = page
        self.selector = selector

    @property
    def first(self) -> FakeLocator:
        return self

    def is_visible(self, timeout: int | None = None) -> bool:
        return self.selector in self.page.visible_fields

    def click(self, timeout: int | None = None) -> None:
        if not self.is_visible():
            raise FakeTimeoutError(f"Timeout: {self.selector} niewidoczny")
        self.page.clicked.append(self.selector)

    def fill(self, value: str, timeout: int | None = None) -> None:
        if not self.is_visible():
            raise FakeTimeoutError(f"Timeout: {self.selector} niewidoczny")
        self.page.filled[self.selector] = value


class FakePage:
    """Strona, ktorej widoczne elementy zmieniaja sie w czasie.

    timeline: lista (czas_ms, zbior_widocznych_selektorow) - strona pokazuje
    ostatni stan, ktorego czas juz uplynal. Zegar przesuwaja wait_for_timeout
    (polling w kodzie produkcyjnym) oraz test (symulacja czasu, w ktorym
    uzytkownik czeka na SMS i wpisuje kod).
    """

    def __init__(self, timeline: list[tuple[int, frozenset[str]]]):
        self.timeline = sorted(timeline)
        self.clock_ms = 0
        self.filled: dict[str, str] = {}
        self.clicked: list[str] = []

    @property
    def visible_fields(self) -> frozenset[str]:
        current: frozenset[str] = frozenset()
        for start_ms, visible in self.timeline:
            if self.clock_ms >= start_ms:
                current = visible
        return current

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def wait_for_timeout(self, ms: int) -> None:
        self.clock_ms += ms


class TestHandleSmsCode:
    def test_kod_trafia_do_pola_na_stronie_sms_mimo_nawigacji(self):
        """Race z realnego przebiegu: handle_sms_code startuje tuz po kliknieciu
        'Zaloguj', gdy przegladarka wciaz pokazuje formularz logowania.
        Strona SMS laduje sie po 3 s, a uzytkownik wpisuje kod po 30 s.
        Kod musi trafic do pola kodu na stronie SMS - nie do pola username.
        """
        page = FakePage([(0, LOGIN_PAGE), (3000, SMS_PAGE)])

        def user_types_code(prompt: str) -> str:
            page.clock_ms += 30_000  # uzytkownik czeka na SMS i wpisuje kod
            return "123456"

        result = handle_sms_code(page, label="logowanie", prompt_func=user_types_code)

        assert result is True
        assert page.filled == {'input[id*="kod"]': "123456"}
        assert 'button:has-text("Potwierdź")' in page.clicked

    def test_nie_pyta_o_kod_gdy_widoczny_formularz_logowania(self):
        """Formularz logowania (widoczne pole hasla) nie moze byc brany
        za formularz kodu SMS - prompt nie powinien sie pojawic."""
        page = FakePage([(0, LOGIN_PAGE)])

        def unexpected_prompt(prompt: str) -> str:
            pytest.fail("Prompt o kod SMS nie powinien byc wywolany na stronie logowania")

        result = handle_sms_code(
            page, label="logowanie", prompt_func=unexpected_prompt, timeout_ms=6000
        )

        assert result is False
        assert page.filled == {}

    def test_zwraca_false_gdy_pole_kodu_znika_po_prompcie(self):
        """Jesli w czasie wpisywania kodu strona zmieni sie tak, ze pole kodu
        znika (np. sesja wygasla), funkcja ma zwrocic False i poprosic
        o reczne wpisanie - a nie wisiec i rzucac wyjatkiem."""
        page = FakePage([(0, SMS_PAGE), (10_000, frozenset())])

        def user_types_code(prompt: str) -> str:
            page.clock_ms += 30_000
            return "123456"

        result = handle_sms_code(page, label="podpis", prompt_func=user_types_code)

        assert result is False
        assert page.filled == {}

    def test_wypelnia_pole_gdy_formularz_sms_od_razu_widoczny(self):
        """Sciezka szczesliwa: formularz SMS jest juz na ekranie,
        kod trafia do pola i Potwierdz zostaje klikniete."""
        page = FakePage([(0, SMS_PAGE)])

        result = handle_sms_code(page, label="podpis", prompt_func=lambda _: "654321")

        assert result is True
        assert page.filled == {'input[id*="kod"]': "654321"}
        assert 'button:has-text("Potwierdź")' in page.clicked

    def test_zwraca_false_gdy_uzytkownik_nie_poda_kodu(self):
        """Pusty kod (Enter bez wpisania) = uzytkownik wpisze recznie."""
        page = FakePage([(0, SMS_PAGE)])

        result = handle_sms_code(page, label="podpis", prompt_func=lambda _: "  ")

        assert result is False
        assert page.filled == {}
