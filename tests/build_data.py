"""Builds verifier/data.py from the frozen ECB snapshot in tests/ecb/.

    uv run python tests/build_data.py

The snapshot is eurofxref-hist.csv from https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip, downloaded
on SNAPSHOT_DAY and checked against SHA256 before anything is read. Each row is one day the ECB published its euro
reference rates: the date, then for each currency the number of its units one euro buys, or N/A when the ECB gave
no rate for it that day. The rules:

- A publication day is a row; a day with no row (a weekend or a TARGET holiday) has no rates.
- A rate is kept exactly as the ECB wrote it, as text, so no digit is lost; N/A becomes "-".
- The euro itself is not a column: one euro is always one euro.

CURRENCIES, written by hand, gives each currency's English name, its Chinese name and the other names people call it
by. Some of those names belong to several currencies ("dollar", "krone"): a name that does is ambiguous.
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

# code -> (English name, Chinese name, other names); the ECB's currencies, and the euro
CURRENCIES = {
    "AUD": ("Australian dollar", "澳大利亚元", ["dollar", "aussie dollar", "澳元"]),
    "BGN": ("Bulgarian lev", "保加利亚列弗", ["lev", "列弗"]),
    "BRL": ("Brazilian real", "巴西雷亚尔", ["real", "reais", "雷亚尔"]),
    "CAD": ("Canadian dollar", "加拿大元", ["dollar", "loonie", "加元"]),
    "CHF": ("Swiss franc", "瑞士法郎", ["franc", "瑞郎"]),
    "CNY": ("Chinese yuan renminbi", "人民币", ["yuan", "renminbi", "rmb", "chinese yuan", "元"]),
    "CYP": ("Cyprus pound", "塞浦路斯镑", ["pound", "cypriot pound"]),
    "CZK": ("Czech koruna", "捷克克朗", ["koruna", "克朗"]),
    "DKK": ("Danish krone", "丹麦克朗", ["krone", "克朗"]),
    "EEK": ("Estonian kroon", "爱沙尼亚克朗", ["kroon", "克朗"]),
    "EUR": ("Euro", "欧元", ["euro"]),
    "GBP": ("Pound sterling", "英镑", ["pound", "british pound", "sterling"]),
    "HKD": ("Hong Kong dollar", "港元", ["dollar", "港币"]),
    "HRK": ("Croatian kuna", "克罗地亚库纳", ["kuna", "库纳"]),
    "HUF": ("Hungarian forint", "匈牙利福林", ["forint", "福林"]),
    "IDR": ("Indonesian rupiah", "印度尼西亚盾", ["rupiah", "印尼盾"]),
    "ILS": ("Israeli shekel", "以色列新谢克尔", ["shekel", "new shekel", "谢克尔"]),
    "INR": ("Indian rupee", "印度卢比", ["rupee", "卢比"]),
    "ISK": ("Icelandic krona", "冰岛克朗", ["krona", "克朗"]),
    "JPY": ("Japanese yen", "日元", ["yen", "日币"]),
    "KRW": ("South Korean won", "韩元", ["won", "korean won"]),
    "LTL": ("Lithuanian litas", "立陶宛立特", ["litas"]),
    "LVL": ("Latvian lats", "拉脱维亚拉特", ["lats"]),
    "MTL": ("Maltese lira", "马耳他里拉", ["lira", "里拉"]),
    "MXN": ("Mexican peso", "墨西哥比索", ["peso", "比索"]),
    "MYR": ("Malaysian ringgit", "马来西亚林吉特", ["ringgit", "林吉特"]),
    "NOK": ("Norwegian krone", "挪威克朗", ["krone", "克朗"]),
    "NZD": ("New Zealand dollar", "新西兰元", ["dollar", "纽元"]),
    "PHP": ("Philippine peso", "菲律宾比索", ["peso", "比索"]),
    "PLN": ("Polish zloty", "波兰兹罗提", ["zloty", "兹罗提"]),
    "ROL": ("Romanian old leu", "罗马尼亚旧列伊", ["leu", "列伊"]),
    "RON": ("Romanian leu", "罗马尼亚列伊", ["leu", "列伊"]),
    "RUB": ("Russian rouble", "俄罗斯卢布", ["rouble", "ruble", "russian ruble", "卢布"]),
    "SEK": ("Swedish krona", "瑞典克朗", ["krona", "克朗"]),
    "SGD": ("Singapore dollar", "新加坡元", ["dollar", "新元"]),
    "SIT": ("Slovenian tolar", "斯洛文尼亚托拉尔", ["tolar"]),
    "SKK": ("Slovak koruna", "斯洛伐克克朗", ["koruna", "克朗"]),
    "THB": ("Thai baht", "泰铢", ["baht"]),
    "TRL": ("Turkish old lira", "土耳其旧里拉", ["lira", "里拉"]),
    "TRY": ("Turkish lira", "土耳其里拉", ["lira", "里拉"]),
    "USD": ("US dollar", "美元", ["dollar", "american dollar", "us dollar", "u.s. dollar", "美金"]),
    "ZAR": ("South African rand", "南非兰特", ["rand", "兰特"]),
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
        "# code -> (English name, Chinese name, other names)",
        "CURRENCIES = {",
        *(
            f"    {quoted(code)}: ({quoted(name)}, {quoted(chinese)}, [{', '.join(map(quoted, others))}]),"
            for code, (name, chinese, others) in CURRENCIES.items()
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
