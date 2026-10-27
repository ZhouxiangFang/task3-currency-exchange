"""Builds verifier/data.py from the frozen ECB snapshot in tests/ecb/.

    uv run python tests/build_data.py

The snapshot is eurofxref-hist.csv from https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip, downloaded
on SNAPSHOT_DAY and checked against SHA256 before anything is read. Each row is one day the ECB published its euro
reference rates: the date, then for each currency the number of its units one euro buys, or N/A when the ECB gave
no rate for it that day. The rules:

- A publication day is a row; a day with no row (a weekend or a TARGET holiday) has no rates.
- A rate is kept exactly as the ECB wrote it, as text, so no digit is lost; N/A becomes "-".
- The euro itself is not a column: one euro is always one euro.

CURRENCIES lists each currency's English name and aliases. Some of those names belong to several currencies ("dollar", "krone"): a name that does is ambiguous.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
SNAPSHOT = HERE / "ecb" / "eurofxref-hist.csv"
TARGET = HERE.parent / "verifier" / "data.py"
SNAPSHOT_DAY = "2026-10-26"
SHA256 = "510c545c3ffe7efb3f0918355ed916e3bd89d3f2feef0382c3eb97be5b6ca426"
MISSING = "N/A"

# code -> (English name, aliases); the ECB's currencies, and the euro
CURRENCIES = {
    "AUD": ("Australian dollar", ["dollar", "aussie dollar"]),
    "BGN": ("Bulgarian lev", ["lev"]),
    "BRL": ("Brazilian real", ["real", "reais"]),
    "CAD": ("Canadian dollar", ["dollar", "loonie"]),
    "CHF": ("Swiss franc", ["franc"]),
    "CNY": ("Chinese yuan renminbi", ["yuan", "renminbi", "rmb", "chinese yuan"]),
    "CYP": ("Cyprus pound", ["pound", "cypriot pound"]),
    "CZK": ("Czech koruna", ["koruna"]),
    "DKK": ("Danish krone", ["krone"]),
    "EEK": ("Estonian kroon", ["kroon"]),
    "EUR": ("Euro", ["euro"]),
    "GBP": ("Pound sterling", ["pound", "british pound", "sterling"]),
    "HKD": ("Hong Kong dollar", ["dollar"]),
    "HRK": ("Croatian kuna", ["kuna"]),
    "HUF": ("Hungarian forint", ["forint"]),
    "IDR": ("Indonesian rupiah", ["rupiah"]),
    "ILS": ("Israeli shekel", ["shekel", "new shekel"]),
    "INR": ("Indian rupee", ["rupee"]),
    "ISK": ("Icelandic krona", ["krona"]),
    "JPY": ("Japanese yen", ["yen"]),
    "KRW": ("South Korean won", ["won", "korean won"]),
    "LTL": ("Lithuanian litas", ["litas"]),
    "LVL": ("Latvian lats", ["lats"]),
    "MTL": ("Maltese lira", ["lira"]),
    "MXN": ("Mexican peso", ["peso"]),
    "MYR": ("Malaysian ringgit", ["ringgit"]),
    "NOK": ("Norwegian krone", ["krone"]),
    "NZD": ("New Zealand dollar", ["dollar"]),
    "PHP": ("Philippine peso", ["peso"]),
    "PLN": ("Polish zloty", ["zloty"]),
    "ROL": ("Romanian old leu", ["leu"]),
    "RON": ("Romanian leu", ["leu"]),
    "RUB": ("Russian rouble", ["rouble", "ruble", "russian ruble"]),
    "SEK": ("Swedish krona", ["krona"]),
    "SGD": ("Singapore dollar", ["dollar"]),
    "SIT": ("Slovenian tolar", ["tolar"]),
    "SKK": ("Slovak koruna", ["koruna"]),
    "THB": ("Thai baht", ["baht"]),
    "TRL": ("Turkish old lira", ["lira"]),
    "TRY": ("Turkish lira", ["lira"]),
    "USD": ("US dollar", ["dollar", "american dollar", "us dollar", "u.s. dollar"]),
    "ZAR": ("South African rand", ["rand"]),
}


def read_snapshot() -> list[list[str]]:
    data = SNAPSHOT.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit("tests/ecb/eurofxref-hist.csv is not the pinned snapshot: its SHA-256 differs")
    return list(csv.reader(data.decode("utf-8").splitlines()))


def build() -> tuple[list[str], dict[str, list[str]]]:
    """Every publication day, oldest first, and each currency's rates aligned with them ("-" for none)."""
    header, *rows = read_snapshot()
    codes = [code for code in header[1:] if code]
    rows.sort(key=lambda row: row[0])
    dates = [row[0] for row in rows]
    rates = {code: [] for code in sorted(codes)}
    for row in rows:
        for code, rate in zip(codes, row[1:]):
            rates[code].append("-" if rate == MISSING else rate)
    return dates, rates


def quoted(text: str) -> str:
    """``text`` as a double-quoted Python string, the way ruff formats one."""
    return json.dumps(text, ensure_ascii=False)


def render(dates: list[str], rates: dict[str, list[str]]) -> str:
    lines = [
        '"""The ECB euro reference rates and the currencies they cover: a frozen snapshot, built by tests/build_data.py',
        f"from tests/ecb/eurofxref-hist.csv (downloaded {SNAPSHOT_DAY}), which says how.",
        "",
        "This is the one copy of the data. The plugin's tools read it, and the verifier judges every tool output and every",
        "answer against it, so no verdict trusts what a tool returned.",
        "",
        f'{len(dates)} publication days, {dates[0]} to {dates[-1]}; {len(rates)} currencies besides the euro."""',
        "",
        "# code -> (English name, aliases)",
        "CURRENCIES = {",
        *(
            f"    {quoted(code)}: ({quoted(name)}, [{', '.join(map(quoted, others))}]),"
            for code, (name, others) in CURRENCIES.items()
        ),
        "}",
        "",
        "# every publication day, oldest first, space-separated",
        f"DATES = {quoted(' '.join(dates))}",
        "",
        "# code -> its rate on each publication day, in DATES' order, space-separated: units per euro, or - for none",
        "RATES = {",
        *(f"    {quoted(code)}: {quoted(' '.join(values))}," for code, values in rates.items()),
        "}",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    TARGET.write_text(render(*build()), encoding="utf-8")
    print(f"wrote {TARGET}")
