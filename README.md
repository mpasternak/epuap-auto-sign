# epuap-auto-sign

[![Tests](https://github.com/mpasternak/epuap-auto-sign/actions/workflows/tests.yml/badge.svg)](https://github.com/mpasternak/epuap-auto-sign/actions/workflows/tests.yml)

**Automatyzacja podpisywania dokumentów PDF podpisem zaufanym (Profil Zaufany)** przez portal [podpis.gov.pl](https://podpis.gov.pl/).

Skrypt otwiera przeglądarkę Chromium, automatycznie uploaduje plik, klika wszystkie niezbędne przyciski, wypełnia formularz logowania danymi z pliku konfiguracyjnego, zapamiętuje pozycję graficznego znaku podpisu dla każdego pliku (lub wzorca plików) i pobiera podpisany dokument. Użytkownik musi tylko wpisać dwa kody SMS (do logowania i do podpisu).

## Po co to jest?

Jeśli regularnie podpisujesz te same dokumenty podpisem zaufanym (np. protokoły, faktury, wnioski), cały proces przez [podpis.gov.pl](https://podpis.gov.pl/) wymaga sporo kliknięć i przeciągania myszką. Ten pakiet eliminuje tę żmudną pracę — pozostaje tylko wpisanie dwóch kodów SMS.

Narzędzie jest szczególnie przydatne, gdy:

- Podpisujesz wiele plików o tym samym schemacie nazewnictwa (np. `protokol_*.pdf`) i potrzebujesz tego samego położenia znaku podpisu dla wszystkich.
- Chcesz przyspieszyć proces podpisywania bez rezygnowania z oficjalnego portalu rządowego.
- Potrzebujesz skryptowego podpisywania dokumentów (np. w ramach większego pipeline'u przetwarzania plików).

## Wymagania

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (zalecany menedżer środowisk Python)
- Aktywny Profil Zaufany
- Dostęp do SMS-ów autoryzacyjnych (kody do logowania i podpisywania)

## Instalacja

### Opcja A: Jako narzędzie systemowe (zalecana)

```bash
git clone https://github.com/mpasternak/epuap-auto-sign.git
cd epuap-auto-sign
uv tool install .
uv run playwright install chromium
```

Od teraz `epuap-sign` jest dostępne w PATH.

### Opcja B: Lokalne środowisko

```bash
git clone https://github.com/mpasternak/epuap-auto-sign.git
cd epuap-auto-sign
uv sync
uv run playwright install chromium
```

W tym trybie uruchamiasz przez `uv run epuap-sign ...`.

## Konfiguracja

Skopiuj plik przykładowy i wypełnij swoimi danymi:

```bash
cp config.toml.example config.toml
```

Zawartość `config.toml`:

```toml
[credentials]
username = "twoj_login_pz"
password = "twoje_haslo"

[signature]
# Domyślna pozycja znaku podpisu (procenty strony dokumentu)
x = 50
y = 66

# Opcjonalnie: pozycje per plik lub wzorzec (glob)
# Skrypt sam je zapisuje po pierwszym użyciu danego pliku.
# Możesz ręcznie zamienić pełną ścieżkę na wzorzec glob.
#
# [signatures."/Users/jan/protokol_*.pdf"]
# x = 50.0
# y = 66.0
```

**UWAGA:** Plik `config.toml` zawiera dane logowania — jest w `.gitignore`, **nigdy nie commituj go do repozytorium**.

## Użycie

### Podstawowe podpisywanie

```bash
epuap-sign dokument.pdf
```

Wynik: `dokument_signed.pdf` w tym samym katalogu.

### Z dodatkowymi opcjami

```bash
# Własna ścieżka pliku wyjściowego
epuap-sign dokument.pdf -o podpisany.pdf

# Dłuższy timeout (domyślnie 300s = 5 minut)
epuap-sign dokument.pdf -t 600

# Szczegółowe logowanie
epuap-sign dokument.pdf -v

# Własna pozycja podpisu (procenty strony)
epuap-sign dokument.pdf -x 70 -y 85

# Inna metoda podpisu
epuap-sign dokument.pdf -m "Certyfikat kwalifikowany"

# Inna ścieżka do konfiguracji
epuap-sign dokument.pdf -c /ścieżka/do/config.toml
```

### Wszystkie opcje

```
epuap-sign [-h] [-o OUTPUT] [-t TIMEOUT] [-c CONFIG]
           [-m METHOD] [-x SIG_X] [-y SIG_Y] [-v] pdf

Argumenty:
  pdf                   Ścieżka do pliku PDF do podpisania

Opcje:
  -h, --help            Wyświetl pomoc
  -o, --output          Ścieżka pliku wyjściowego
                        (domyślnie: <nazwa>_signed.pdf)
  -t, --timeout         Czas oczekiwania w sekundach (domyślnie: 300)
  -c, --config          Ścieżka do config.toml (domyślnie: ./config.toml)
  -m, --method          Metoda podpisu (domyślnie: "Profil zaufany")
  -x, --sig-x           Pozycja pozioma podpisu (0-100, domyślnie: 50)
  -y, --sig-y           Pozycja pionowa podpisu (0-100, domyślnie: 66)
  -v, --verbose         Szczegółowe logowanie (DEBUG)
```

## Jak to działa — krok po kroku

1. **Otwarcie przeglądarki Chromium** i załadowanie strony `podpis.gov.pl/podpisz-dokument-elektronicznie/`.
2. **Zamknięcie okna klauzuli RODO** — skrypt klika „Zamknij".
3. **Upload pliku PDF** do ukrytego pola `<input type="file">`.
4. **Kliknięcie „Dalej"** po pojawieniu się pliku na liście.
5. **Kliknięcie „pokaż podgląd dokumentu"** i oczekiwanie na załadowanie podglądu.
6. **Przeciągnięcie znaku graficznego podpisu** (`#signature` z Angular CDK Drag) na zadaną pozycję procentową wewnątrz kontenera `.boundary`.
7. **Pauza na weryfikację** — użytkownik może ręcznie poprawić pozycję w oknie przeglądarki.
8. **Odczyt i zapis końcowej pozycji** do `config.toml` (pod pełną ścieżką pliku).
9. **Kliknięcie „Zapisz"** — powrót do ekranu „Sprawdź dokumenty przed podpisaniem".
10. **Kliknięcie „Podpisz"** i **wybór metody** („Profil zaufany").
11. **Wypełnienie formularza logowania** danymi z `config.toml`.
12. **Pytanie o kod SMS (logowanie)** w terminalu — dźwiękowy alarm (`\a`).
13. **Pytanie o kod SMS (podpis)** — drugi kod.
14. **Kliknięcie „Pobierz podpisane dokumenty"** i zapisanie pliku.

### Mechanizm zapamiętywania pozycji podpisu

Przy pierwszym podpisywaniu danego pliku skrypt używa domyślnej pozycji (`[signature]` z config lub flag `-x`/`-y`). Po ręcznej weryfikacji/korekcie (krok 7), końcowa pozycja jest zapisywana do `config.toml` pod kluczem pełnej ścieżki pliku:

```toml
[signatures."/Users/jan/protokol_03.2026.pdf"]
x = 52.3
y = 55.2
```

Przy kolejnym uruchomieniu tego samego pliku skrypt użyje zapamiętanej pozycji. Możesz też ręcznie **zamienić pełną ścieżkę na wzorzec glob**, aby jedna pozycja pasowała do wielu plików:

```toml
[signatures."/Users/jan/protokol_*.pdf"]
x = 52.3
y = 55.2
```

Kolejność sprawdzania:
1. Pasujący wzorzec w `[signatures]` (pierwszy pasujący wygrywa).
2. Globalne `[signature]`.
3. Wartości z `-x`/`-y` lub domyślne (50, 66).

## Struktura projektu

```
epuap-auto-sign/
├── src/epuap_auto_sign/
│   ├── __init__.py         # Publiczne API pakietu
│   ├── cli.py              # Interfejs wiersza poleceń (argparse)
│   ├── signer.py           # Orkiestracja całego procesu podpisywania
│   ├── browser.py          # Pomocnicze funkcje Playwright (wait_and_click)
│   ├── login.py            # Logowanie + obsługa kodów SMS
│   ├── signature.py        # Pozycjonowanie znaku graficznego podpisu
│   ├── config.py           # Ładowanie/zapis konfiguracji TOML
│   └── constants.py        # Stałe (URL-e, timeouty, wartości domyślne)
├── tests/
│   ├── test_config.py      # Testy konfiguracji + matchingu wzorców
│   ├── test_signature.py   # Testy obliczeń pozycji (target + reverse)
│   ├── test_cli.py         # Testy parsera CLI
│   └── test_signer_path.py # Testy wyznaczania ścieżki wyjściowej
├── .github/workflows/
│   └── tests.yml           # CI: pytest + ruff
├── config.toml.example     # Przykładowa konfiguracja
├── pyproject.toml          # Metadane pakietu
├── README.md               # Ten plik
└── LICENSE                 # MIT
```

## Uruchamianie testów

```bash
# Wszystkie testy
uv run pytest tests/ -v

# Z pokryciem
uv run pytest tests/ --cov=epuap_auto_sign --cov-report=term-missing

# Lint
uv run ruff check src/ tests/
```

## Ograniczenia i uwagi

- **Interakcja użytkownika wymagana**: dwa kody SMS (logowanie + podpis) muszą być wpisane ręcznie w terminalu.
- **Automatyzacja odczytu SMS**: istnieje eksperymentalny projekt [chrome-messages-reader](https://github.com/mpasternak/chrome-messages-reader), który miał wyciągać kody SMS z Google Messages for Web działającego w Chrome. W praktyce okazało się to trudne do niezawodnej realizacji — integracja pozostaje otwarta.
- **Format wyjściowy**: domyślnie PDF (`_signed.pdf`). Jeśli portal zwróci inny format, skrypt dopasuje rozszerzenie.
- **Zmiany strony gov.pl**: selektory są oparte na analizie obecnej wersji portalu. Jeśli `podpis.gov.pl` zmieni strukturę HTML, może być konieczna aktualizacja selektorów w modułach `browser.py`, `login.py`, `signature.py`.
- **Reverse engineering**: rozwiązanie bazuje na automatyzacji przeglądarki, nie oficjalnym API. Oficjalne SOAP API (TpSigning2/3) wymaga rejestracji systemu zewnętrznego i certyfikatu X.509, a do tego podpisuje tylko pliki XML.
- **Bezpieczeństwo**: `config.toml` zawiera hasło w postaci jawnej. Trzymaj go poza repozytorium (jest w `.gitignore`) i zadbaj o uprawnienia plików (`chmod 600 config.toml`).

## Ciąg dalszy (TODO)

- [ ] Automatyczny odczyt kodu SMS — patrz eksperymentalny [chrome-messages-reader](https://github.com/mpasternak/chrome-messages-reader).
- [ ] Obsługa wielu plików w jednej sesji (batch mode).
- [ ] Tryb headless dla zaawansowanych użytkowników.
- [ ] Wsparcie dla innych metod podpisu (Certyfikat kwalifikowany, e-dowód).

## Licencja

MIT — patrz plik [LICENSE](LICENSE).

## Bezpieczeństwo

Jeśli znajdziesz lukę bezpieczeństwa, zgłoś ją przez GitHub Issues oznaczając jako **security**.

## Wkład

Pull requesty mile widziane. Przed zgłoszeniem PR:

```bash
uv run ruff check src/ tests/ --fix
uv run pytest tests/
```
