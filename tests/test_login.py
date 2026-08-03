"""Testy modulu login - obsluga kodu SMS.

Fake'i modeluja kluczowe wlasciwosci Playwright:

- Locator jest "zywy": selektor jest rozwiazywany od nowa przy kazdej akcji,
  na aktualnym stanie strony.
- is_visible() NIE wykrywa przykrycia elementu (np. backdropem modala) -
  element pod modalem wciaz jest "widoczny". Przykrycie wykrywa dopiero
  proba akcji (click), ktora konczy sie timeoutem.

Widocznosc to uproszczenie: strona trzyma slownik selektor -> FakeField
dla elementow, ktore "pasuja do widocznego elementu" w danej chwili.
"""

from __future__ import annotations

import pytest

from epuap_auto_sign.login import handle_sms_code


class FakeTimeoutError(Exception):
    """Odpowiednik playwright TimeoutError przy akcji na niedostepnym elemencie."""


class FakeField:
    """Jeden widoczny element (input/przycisk) na stronie.

    occluded=True modeluje element przykryty backdropem modala:
    is_visible() dalej zwraca True, ale click/fill koncza sie timeoutem.
    """

    def __init__(self, value: str = "", occluded: bool = False):
        self.value = value
        self.occluded = occluded


class FakeLocator:
    """Imituje Locator Playwright: rozwiazuje selektor przy kazdej akcji."""

    def __init__(self, page: FakePage, selector: str):
        self.page = page
        self.selector = selector

    @property
    def first(self) -> FakeLocator:
        return self

    def _field(self) -> FakeField | None:
        return self.page.fields.get(self.selector)

    def is_visible(self, timeout: int | None = None) -> bool:
        return self._field() is not None

    def input_value(self, timeout: int | None = None) -> str:
        field = self._field()
        if field is None:
            raise FakeTimeoutError(f"Timeout: {self.selector} nie istnieje")
        return field.value

    def click(self, timeout: int | None = None, trial: bool = False) -> None:
        field = self._field()
        if field is None or field.occluded:
            raise FakeTimeoutError(f"Timeout: {self.selector} nieklikalny")
        if not trial:
            self.page.clicked.append(self.selector)

    def fill(self, value: str, timeout: int | None = None) -> None:
        field = self._field()
        if field is None or field.occluded:
            raise FakeTimeoutError(f"Timeout: {self.selector} niedostepny")
        field.value = value
        self.page.filled[self.selector] = value


class FakePage:
    """Strona, ktorej widoczne elementy zmieniaja sie w czasie.

    timeline: lista (czas_ms, slownik selektor -> FakeField) - strona pokazuje
    ostatni stan, ktorego czas juz uplynal. Zegar przesuwaja wait_for_timeout
    (polling w kodzie produkcyjnym) oraz test (symulacja czasu, w ktorym
    uzytkownik czeka na SMS i wpisuje kod).
    """

    def __init__(self, timeline: list[tuple[int, dict[str, FakeField]]]):
        self.timeline = sorted(timeline, key=lambda item: item[0])
        self.clock_ms = 0
        self.filled: dict[str, str] = {}
        self.clicked: list[str] = []

    @property
    def fields(self) -> dict[str, FakeField]:
        current: dict[str, FakeField] = {}
        for start_ms, fields in self.timeline:
            if self.clock_ms >= start_ms:
                current = fields
        return current

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def wait_for_timeout(self, ms: int) -> None:
        self.clock_ms += ms


def login_form_fields(occluded: bool = False) -> dict[str, FakeField]:
    """Formularz logowania z wypelnionymi polami (po fill_login_form)."""
    return {
        'input[type="text"]': FakeField(value="jan.kowalski", occluded=occluded),
        'input[type="password"]': FakeField(value="tajnehaslo", occluded=occluded),
    }


def sms_modal_fields() -> dict[str, FakeField]:
    """Modal 'Potwierdz logowanie' z pustym polem kodu SMS."""
    return {
        'input[id*="sms"]': FakeField(),
        'button:has-text("Potwierdź")': FakeField(),
    }


class TestHandleSmsCode:
    def test_kod_trafia_do_pola_w_modalu_nad_formularzem_logowania(self):
        """Realny przebieg z pz.gov.pl: po kliknieciu 'Zaloguj' NIE ma nawigacji -
        po 3 s nad formularzem logowania otwiera sie modal 'Potwierdz logowanie'
        z pustym polem kodu SMS. Pola loginu i hasla pod backdropem wciaz sa
        'widoczne' dla Playwrighta, ale nieklikalne. Kod musi trafic do pola
        w modalu, a wypelnione pole username ma zostac nietkniete.
        """
        page = FakePage(
            [
                (0, login_form_fields()),
                (3000, {**login_form_fields(occluded=True), **sms_modal_fields()}),
            ]
        )

        def user_types_code(prompt: str) -> str:
            page.clock_ms += 30_000  # uzytkownik czeka na SMS i wpisuje kod
            return "123456"

        result = handle_sms_code(page, label="logowanie", prompt_func=user_types_code)

        assert result is True
        assert page.filled == {'input[id*="sms"]': "123456"}
        assert 'button:has-text("Potwierdź")' in page.clicked
        assert page.fields['input[type="text"]'].value == "jan.kowalski"

    def test_kod_trafia_do_pola_na_nowej_stronie_po_nawigacji(self):
        """Wariant z pelna nawigacja: strona SMS zastepuje strone logowania
        po 3 s, a uzytkownik wpisuje kod po 30 s. Kod musi trafic do pola
        kodu na nowej stronie."""
        sms_page = {
            'input[id*="kod"]': FakeField(),
            'button:has-text("Potwierdź")': FakeField(),
        }
        page = FakePage([(0, login_form_fields()), (3000, sms_page)])

        def user_types_code(prompt: str) -> str:
            page.clock_ms += 30_000
            return "123456"

        result = handle_sms_code(page, label="logowanie", prompt_func=user_types_code)

        assert result is True
        assert page.filled == {'input[id*="kod"]': "123456"}
        assert 'button:has-text("Potwierdź")' in page.clicked

    def test_nie_pyta_o_kod_gdy_widoczny_tylko_formularz_logowania(self):
        """Wypelniony formularz logowania (bez modala SMS) nie moze byc brany
        za formularz kodu - prompt nie powinien sie pojawic."""
        page = FakePage([(0, login_form_fields())])

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
        page = FakePage([(0, sms_modal_fields()), (10_000, {})])

        def user_types_code(prompt: str) -> str:
            page.clock_ms += 30_000
            return "123456"

        result = handle_sms_code(page, label="podpis", prompt_func=user_types_code)

        assert result is False
        assert page.filled == {}

    def test_wypelnia_pole_gdy_formularz_sms_od_razu_widoczny(self):
        """Sciezka szczesliwa: formularz SMS jest juz na ekranie,
        kod trafia do pola i Potwierdz zostaje klikniete."""
        page = FakePage([(0, sms_modal_fields())])

        result = handle_sms_code(page, label="podpis", prompt_func=lambda _: "654321")

        assert result is True
        assert page.filled == {'input[id*="sms"]': "654321"}
        assert 'button:has-text("Potwierdź")' in page.clicked

    def test_zwraca_false_gdy_uzytkownik_nie_poda_kodu(self):
        """Pusty kod (Enter bez wpisania) = uzytkownik wpisze recznie."""
        page = FakePage([(0, sms_modal_fields())])

        result = handle_sms_code(page, label="podpis", prompt_func=lambda _: "  ")

        assert result is False
        assert page.filled == {}
