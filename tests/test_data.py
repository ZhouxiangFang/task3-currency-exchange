"""The data and the tools: the snapshot is the pinned one and data.py is built from it, every rule the verifier uses
agrees with one written apart from it (the csv module, datetime, fractions, a linear scan), names mean the currencies
worked out by hand, and the tools are true to the data."""

from __future__ import annotations

import csv
import datetime
import random
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

import pytest
from build_data import CURRENCIES, SNAPSHOT, TARGET, build, render

from contract import CalculateInput, CurrencyInput, RatesInput, Status
from plugin.rates import calculate, find_currency, get_rates
from verifier.checks import DAYS, evaluate, expected, known_dates, publication, rate_on, real_date, resolve, weekday

ROWS = {row["Date"]: row for row in csv.DictReader(SNAPSHOT.read_text(encoding="utf-8").splitlines())}

# Names worked out by hand from CURRENCIES, each with the codes it means.
NAMES = [
    ("USD", ["USD"]),
    ("usd", ["USD"]),
    (" usd ", ["USD"]),
    ("US dollar", ["USD"]),
    ("us dollars", ["USD"]),  # a plural s is dropped
    ("american dollar", ["USD"]),
    ("Japanese yen", ["JPY"]),
    ("YEN", ["JPY"]),
    ("yen", ["JPY"]),
    ("euros", ["EUR"]),
    ("EUR", ["EUR"]),
    ("renminbi", ["CNY"]),
    ("Pound sterling", ["GBP"]),
    ("sterling", ["GBP"]),
    ("lats", ["LVL"]),  # a name that ends in s
    ("Polish złoty", []),  # the data writes zloty: ł is no accent
    ("polish zloty", ["PLN"]),
    ("dollar", ["AUD", "CAD", "HKD", "NZD", "SGD", "USD"]),
    ("dollars", ["AUD", "CAD", "HKD", "NZD", "SGD", "USD"]),
    ("pound", ["CYP", "GBP"]),
    ("krone", ["DKK", "NOK"]),
    ("lira", ["MTL", "TRL", "TRY"]),
    ("leu", ["ROL", "RON"]),
    ("peso", ["MXN", "PHP"]),
    ("koruna", ["CZK", "SKK"]),
]
NO_CURRENCY = ["Bitcoin", "BTC", "XYZ", "us", "", "   ", "dollarz", "Japanese", "yuan renminbi dollar"]


def rows_rate(code: str, day: str) -> str:
    """A rate read straight off the CSV with the csv module: "1" for the euro, "" for N/A."""
    if code == "EUR":
        return "1"
    value = ROWS[day][code]
    return "" if value == "N/A" else value


def latest_on_or_before(day: str) -> str | None:
    earlier = [each for each in ROWS if each <= day]
    return max(earlier) if earlier else None


def test_the_snapshot_is_the_pinned_one_and_data_py_is_built_from_it() -> None:
    assert TARGET.read_text(encoding="utf-8") == render(*build())


def test_the_data_is_well_formed() -> None:
    assert (len(DAYS), DAYS[0], DAYS[-1]) == (7122, "1999-01-04", "2026-10-26")
    assert DAYS == sorted(set(DAYS)) == sorted(ROWS)
    assert len(CURRENCIES) == 42  # 41 ECB currencies and the euro
    rng = random.Random(580)
    for day in rng.sample(DAYS, 300):
        index = publication(day)
        for code in CURRENCIES:
            assert rate_on(code, index) == rows_rate(code, day)


@pytest.mark.parametrize(
    ("code", "first", "last"),
    [
        ("USD", "1999-01-04", "2026-10-26"),
        ("CYP", "1999-01-04", "2007-12-31"),  # Cyprus took the euro in 2008
        ("BGN", "2000-07-19", "2025-12-31"),  # Bulgaria took the euro in 2026
        ("RUB", "2005-04-01", "2022-03-01"),  # suspended in 2022
        ("RON", "2005-07-01", "2026-10-26"),  # the leu was redenominated in 2005...
        ("ROL", "1999-01-04", "2005-06-30"),  # ...after the old leu
        ("TRY", "2005-01-03", "2026-10-26"),
        ("ISK", "1999-01-04", "2026-10-26"),  # with no rate from 2008-12-10 to 2018-01-31
    ],
)
def test_knows_when_each_currency_has_rates(code: str, first: str, last: str) -> None:
    assert known_dates(code) == (first, last)


def test_iceland_has_no_rate_through_its_crisis() -> None:
    assert rows_rate("ISK", "2008-12-09") and not rows_rate("ISK", "2008-12-10")
    assert not rows_rate("ISK", "2018-01-31") and rows_rate("ISK", "2018-02-01")


@pytest.mark.parametrize(("name", "codes"), NAMES)
def test_a_name_means_the_currencies_worked_out_by_hand(name: str, codes: list[str]) -> None:
    assert resolve(name) == codes


@pytest.mark.parametrize("name", NO_CURRENCY)
def test_a_name_that_means_nothing(name: str) -> None:
    assert resolve(name) == []


def test_dates_and_weekdays_agree_with_datetime() -> None:
    day = datetime.date(1996, 1, 1)
    while day <= datetime.date(2031, 12, 31):
        text = day.isoformat()
        assert real_date(text) == text and weekday(text) == day.strftime("%A")
        day += datetime.timedelta(days=1)
    for bad in ["2021-02-29", "1900-02-29", "2015-13-01", "2015-00-10", "2015-04-31", "2015-3-14", "14/03/2015", ""]:
        assert real_date(bad) is None
    assert real_date("2000-02-29") == "2000-02-29"  # 2000 is a leap year, 1900 is not


def test_the_rate_day_agrees_with_a_linear_scan() -> None:
    day = datetime.date(1998, 12, 25)
    while day <= datetime.date(2026, 11, 3):
        text = day.isoformat()
        index = publication(text)
        assert (DAYS[index] if index >= 0 else None) == latest_on_or_before(text)
        day += datetime.timedelta(days=1)


def test_arithmetic_agrees_with_fractions() -> None:
    rng = random.Random(580)
    for _ in range(300):
        numbers = [Fraction(rng.randint(1, 10**6), 10 ** rng.randint(0, 4)) for _ in range(3)]
        text = [f"{float(n):.4f}".rstrip("0").rstrip(".") for n in numbers]
        exact = Fraction(Decimal(text[0])) * Fraction(Decimal(text[1])) / Fraction(Decimal(text[2]))
        value = Fraction(Decimal(evaluate(f"{text[0]} * {text[1]} / ({text[2]})")))
        assert abs(value - exact) <= abs(exact) * Fraction(1, 10**26)
    assert evaluate("(1 + 2) * 3 - -1") == "10"
    assert evaluate("0.1 + 0.2") == "0.3"
    for bad in ["1/0", "2 *", "(1", "1)", "1e5", "two", "", "1 2"]:
        with pytest.raises(ValueError):
            evaluate(bad)


def convert_by_hand(amount: str, from_code: str, to_code: str, date: str) -> tuple[str, str]:
    """The rate day and the converted amount, read off the CSV and worked out with fractions."""
    day = latest_on_or_before(date)
    exact = (
        Fraction(Decimal(amount))
        * Fraction(Decimal(rows_rate(to_code, day)))
        / Fraction(Decimal(rows_rate(from_code, day)))
    )
    cents = exact * 100
    rounded = cents.numerator // cents.denominator + (1 if cents - int(cents) >= Fraction(1, 2) else 0)
    return day, f"{Decimal(rounded) / 100:.2f}"


def test_conversions_agree_with_the_csv_and_fractions() -> None:
    rng = random.Random(580)
    codes = sorted(CURRENCIES)
    done = 0
    for _ in range(600):
        date = rng.choice(DAYS[:-5])[:8] + f"{rng.randint(1, 28):02d}"
        amount = f"{rng.randint(0, 10**7)}.{rng.randint(0, 99):02d}"
        from_code, to_code = rng.choice(codes), rng.choice(codes)
        status, _, got_from, got_to, rate_date, total = expected(amount, from_code, to_code, date)
        day = latest_on_or_before(date)
        if day is None:
            assert status is Status.DATE_OUT_OF_RANGE
            continue
        if not rows_rate(from_code, day) or not rows_rate(to_code, day):
            assert status is Status.NO_RATE
            continue
        assert status is Status.CONVERTED and (got_from, got_to) == (from_code, to_code)
        assert (rate_date, total) == convert_by_hand(amount, from_code, to_code, date)
        done += 1
    assert done > 300


@pytest.mark.parametrize(
    ("trip", "status", "rate_date", "total"),
    [
        (("1000", "USD", "JPY", "2015-03-14"), Status.CONVERTED, "2015-03-13", "121462.35"),  # a Saturday
        (("1000", "US dollars", "yen", "2015-03-14"), Status.CONVERTED, "2015-03-13", "121462.35"),
        (
            ("100", "american dollar", "renminbi", "2020-01-01"),
            Status.CONVERTED,
            "2019-12-31",
            "696.15",
        ),  # New Year's Day
        (("1", "usd", "usd", "2016-03-25"), Status.CONVERTED, "2016-03-24", "1.00"),  # Good Friday
        (("0", "USD", "JPY", "2020-01-02"), Status.CONVERTED, "2020-01-02", "0.00"),
        (("100", "CYP", "EUR", "2007-12-31"), Status.CONVERTED, "2007-12-31", "170.86"),  # its last day
        (("1", "EUR", "USD", "2026-10-26"), Status.CONVERTED, "2026-10-26", "1.12"),  # the data's last day
        (("1", "EUR", "USD", "1999-01-04"), Status.CONVERTED, "1999-01-04", "1.18"),  # its first
        (("abc", "USD", "EUR", "2020-01-01"), Status.INVALID_AMOUNT, "", ""),
        (("-5", "USD", "EUR", "2020-01-01"), Status.INVALID_AMOUNT, "", ""),
        (("1,000", "USD", "EUR", "2020-01-01"), Status.INVALID_AMOUNT, "", ""),
        (("1", "Bitcoin", "EUR", "2020-01-01"), Status.NO_SUCH_CURRENCY, "", ""),
        (("1", "EUR", "Bitcoin", "2020-01-01"), Status.NO_SUCH_CURRENCY, "", ""),
        (("1", "dollar", "EUR", "2020-01-01"), Status.AMBIGUOUS_CURRENCY, "", ""),
        (("1", "Bitcoin", "dollar", "2020-01-01"), Status.NO_SUCH_CURRENCY, "", ""),  # the from currency first
        (("1", "USD", "EUR", "2021-02-29"), Status.INVALID_DATE, "", ""),
        (("1", "USD", "EUR", "1999-01-01"), Status.DATE_OUT_OF_RANGE, "", ""),  # before the first publication
        (("1", "USD", "EUR", "2026-10-27"), Status.DATE_OUT_OF_RANGE, "", ""),  # after the snapshot
        (("100", "ISK", "EUR", "2010-06-01"), Status.NO_RATE, "", ""),  # Iceland's crisis
        (("100", "RUB", "EUR", "2023-05-05"), Status.NO_RATE, "", ""),  # suspended
        (("100", "BGN", "EUR", "2026-02-02"), Status.NO_RATE, "", ""),  # replaced by the euro
        (("100", "CYP", "EUR", "2008-01-02"), Status.NO_RATE, "", ""),
        (("1000", "TRL", "TRY", "2004-12-31"), Status.NO_RATE, "", ""),  # the new lira came days later
        (("abc", "Bitcoin", "EUR", "2099-01-01"), Status.INVALID_AMOUNT, "", ""),  # the amount first
    ],
)
def test_each_conversion_has_the_status_worked_out_by_hand(trip, status, rate_date, total) -> None:
    got = expected(*trip)
    assert (got[0], got[4], got[5]) == (status, rate_date, total)


def test_finds_every_currency_a_name_may_mean(tmp_path: Path) -> None:
    found = find_currency(CurrencyInput(name="pound"), tmp_path)
    assert found.name == "pound"
    assert [(c.code, c.name, c.first_date, c.last_date) for c in found.currencies] == [
        ("CYP", "Cyprus pound", "1999-01-04", "2007-12-31"),
        ("GBP", "Pound sterling", "1999-01-04", "2026-10-26"),
    ]
    with pytest.raises(ValueError, match="no such currency"):
        find_currency(CurrencyInput(name="Bitcoin"), tmp_path)


def test_gets_the_rates_of_one_day(tmp_path: Path) -> None:
    friday = get_rates(RatesInput(date="2015-03-13", currencies=["JPY", "EUR", "USD"]), tmp_path)
    assert (friday.weekday, friday.published) == ("Friday", True)
    assert [(r.currency, r.rate) for r in friday.rates] == [("JPY", "128.41"), ("EUR", "1"), ("USD", "1.0572")]
    saturday = get_rates(RatesInput(date="2015-03-14", currencies=["USD"]), tmp_path)
    assert (saturday.weekday, saturday.published, saturday.rates) == ("Saturday", False, [])
    crisis = get_rates(RatesInput(date="2010-06-01", currencies=["ISK", "USD"]), tmp_path)
    assert crisis.published and [r.rate for r in crisis.rates] == ["", rows_rate("USD", "2010-06-01")]


@pytest.mark.parametrize(
    ("date", "codes", "error"),
    [
        ("2015-03-13", ["XYZ"], "no such currency"),
        ("2015-03-13", ["usd"], "not ISO codes"),
        ("2015-03-13", [], "at least one"),
        ("2015-03-13", ["USD", "USD"], "once"),
        ("2015-02-30", ["USD"], "invalid date"),
        ("13/03/2015", ["USD"], "invalid date"),
        ("1999-01-03", ["USD"], "out of range"),
        ("2026-10-27", ["USD"], "out of range"),
    ],
)
def test_get_rates_refuses_what_the_data_does_not_cover(date: str, codes: list[str], error: str, tmp_path) -> None:
    with pytest.raises(ValueError, match=error):
        get_rates(RatesInput(date=date, currencies=codes), tmp_path)


def test_calculates_exactly(tmp_path: Path) -> None:
    assert calculate(CalculateInput(expression="1000 * 128.41 / 1.0572"), tmp_path).value.startswith("121462.353")
    with pytest.raises(ValueError, match="division by zero"):
        calculate(CalculateInput(expression="1 / (2 - 2)"), tmp_path)


def test_rounding_is_half_up() -> None:
    # 0.125 at a rate of 1 rounds to 0.13, not to 0.12 as half-even would.
    assert Decimal("0.125").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == Decimal("0.13")
    assert expected("0.125", "EUR", "EUR", "2020-01-02")[5] == "0.13"
