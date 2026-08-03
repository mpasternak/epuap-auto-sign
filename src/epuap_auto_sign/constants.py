"""Stałe używane w pakiecie."""

SIGNER_URL = "https://podpis.gov.pl/podpisz-dokument-elektronicznie/"

POLL_INTERVAL_MS = 2000
STEP_TIMEOUT_MS = 30_000

# Ponowne szukanie pola kodu SMS po zamknieciu prompta - strona jest juz
# zaladowana, wiec wystarczy krotkie okno.
SMS_REFIND_TIMEOUT_MS = 10_000
# Timeout pojedynczej akcji click/fill na polu kodu - zamiast domyslnych 30 s
# Playwrighta, zeby szybko oddac kontrole uzytkownikowi przy problemie.
FIELD_ACTION_TIMEOUT_MS = 5_000

DEFAULT_SIG_X_PCT = 50.0
DEFAULT_SIG_Y_PCT = 66.0
DEFAULT_SIGN_METHOD = "Profil zaufany"
DEFAULT_CONFIG_FILENAME = "config.toml"
