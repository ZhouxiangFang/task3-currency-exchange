"""The verifier, called as NanoAgent's sandbox calls it, with contract instances built from JSON: every answer to the
task and every tool output, judged against the data. The steps the task's instructions describe, played through the
tools, earn a valid verdict on every sampled conversion."""

from __future__ import annotations

import datetime
import random
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output
from test_data import NAMES, NO_CURRENCY

import verifier
from contract import (
    TOOLS,
    CalculateInput,
    ConvertInput,
    ConvertOutput,
    CurrencyInput,
    RatesInput,
    Status,
    Tool,
)
from plugin.rates import calculate, find_currency, get_rates
from verifier.checks import AMOUNT, DAYS, expected

STATUSES = [status.value for status in Status]
EMPTY = {"from_currency": "", "to_currency": "", "rate_date": "", "converted": ""}


def verify(trip: tuple[str, str, str, str], answer: dict) -> dict:
    """The verdict on an answer to the task; there is no reference."""
    amount, from_currency, to_currency, date = trip
    arguments = build_output(
        {"amount": amount, "from_currency": from_currency, "to_currency": to_currency, "date": date}, ConvertInput
    )
    return verifier.verify_task("convert-currency", arguments, build_output(answer, ConvertOutput), None, ".")


def converted(from_code: str, to_code: str, rate_date: str, total: str) -> dict:
    return {
        "status": "converted",
        "from_currency": from_code,
        "to_currency": to_code,
        "rate_date": rate_date,
        "converted": total,
    }


SATURDAY = ("1000", "US dollars", "yen", "2015-03-14")
RIGHT = converted("USD", "JPY", "2015-03-13", "121462.35")


def test_accepts_the_right_conversion() -> None:
    verdict = verify(SATURDAY, RIGHT)
    assert verdict["valid"] is True and verdict["score"] == 1.0, verdict
    # A cent either way allows for rounding on the way; the amount may be written without trailing zeros.
    for total in ["121462.34", "121462.36", "121462.35000", "121462.353"]:
        assert verify(SATURDAY, {**RIGHT, "converted": total})["valid"] is True
    assert verify(("0", "USD", "JPY", "2020-01-02"), converted("USD", "JPY", "2020-01-02", "0"))["valid"] is True


@pytest.mark.parametrize(
    ("answer", "wrong", "score"),
    [
        ({**RIGHT, "converted": "121462.37"}, "converted", 2 / 3),  # two cents off
        ({**RIGHT, "converted": "121000"}, "converted", 2 / 3),
        ({**RIGHT, "converted": "-121462.35"}, "converted", 2 / 3),
        ({**RIGHT, "converted": "121,462.35"}, "converted", 2 / 3),
        ({**RIGHT, "rate_date": "2015-03-14"}, "rate_date", 2 / 3),  # the Saturday itself has no rates
        ({**RIGHT, "rate_date": "2015-03-12"}, "rate_date", 2 / 3),
        ({**RIGHT, "from_currency": "AUD"}, "currencies", 2 / 3),
        ({**RIGHT, "from_currency": "JPY", "to_currency": "USD"}, "currencies", 2 / 3),  # turned around
        ({**RIGHT, "from_currency": "usd"}, "currencies", 2 / 3),
        (converted("USD", "JPY", "2015-03-14", "8.23"), "rate_date, converted", 1 / 3),  # inverted rate, wrong day
        (converted("", "", "", ""), "currencies, rate_date, converted", 0.0),
    ],
)
def test_refuses_a_wrong_conversion_with_partial_credit(answer: dict, wrong: str, score: float) -> None:
    verdict = verify(SATURDAY, answer)
    assert verdict["valid"] is False and verdict["score"] == pytest.approx(score), verdict
    assert verdict["message"].startswith(wrong) and verdict["details"]["expected"]["converted"] == "121462.35"


@pytest.mark.parametrize(
    ("trip", "status"),
    [
        (("abc", "USD", "EUR", "2020-01-01"), "invalid_amount"),
        (("1,000", "USD", "EUR", "2020-01-01"), "invalid_amount"),
        (("1", "Bitcoin", "EUR", "2020-01-01"), "no_such_currency"),
        (("1", "EUR", "us", "2020-01-01"), "no_such_currency"),
        (("1", "dollar", "EUR", "2020-01-01"), "ambiguous_currency"),
        (("1", "EUR", "koruna", "2020-01-01"), "ambiguous_currency"),
        (("1", "USD", "EUR", "2021-02-29"), "invalid_date"),
        (("1", "USD", "EUR", "March 14, 2015"), "invalid_date"),
        (("1", "USD", "EUR", "1999-01-03"), "date_out_of_range"),
        (("1", "USD", "EUR", "2030-01-01"), "date_out_of_range"),
        (("100", "ISK", "EUR", "2010-06-01"), "no_rate"),
        (("100", "EUR", "RUB", "2023-05-05"), "no_rate"),
        (("100", "BGN", "EUR", "2026-02-02"), "no_rate"),
    ],
)
def test_accepts_only_the_status_the_conversion_has(trip, status: str) -> None:
    verdict = verify(trip, {"status": status, **EMPTY})
    assert verdict["valid"] is True and verdict["score"] == 1.0, verdict
    for other in STATUSES:
        if other != status:
            assert verify(trip, {"status": other, **EMPTY})["valid"] is False
    # The other fields go only with converted.
    verdict = verify(trip, {"status": status, **EMPTY, "rate_date": "2020-01-02"})
    assert verdict["valid"] is False and "empty" in verdict["message"]


def test_a_conversion_that_can_be_made_is_never_another_status() -> None:
    for status in STATUSES[1:]:
        assert verify(SATURDAY, {"status": status, **EMPTY})["valid"] is False


@pytest.mark.parametrize("name", NO_CURRENCY)
def test_a_name_that_means_nothing_is_no_such_currency(name: str) -> None:
    assert verify(("1", name, "EUR", "2020-01-02"), {"status": "no_such_currency", **EMPTY})["valid"] is True
    assert verify(("1", "EUR", name, "2020-01-02"), {"status": "no_such_currency", **EMPTY})["valid"] is True


def follow_instructions(trip: tuple[str, str, str, str], tmp_path: Path) -> dict:
    """The answer the task's instructions lead to, through the tools."""
    amount, from_currency, to_currency, date = trip
    if not AMOUNT.fullmatch(amount.strip()):
        return {"status": "invalid_amount", **EMPTY}
    codes = []
    for name in (from_currency, to_currency):
        try:
            found = find_currency(CurrencyInput(name=name), tmp_path).currencies
        except ValueError:
            return {"status": "no_such_currency", **EMPTY}
        if len(found) > 1:
            return {"status": "ambiguous_currency", **EMPTY}
        codes.append(found[0].code)
    currencies = list(dict.fromkeys(codes))
    days = []
    try:
        days.append(get_rates(RatesInput(date=date, currencies=currencies), tmp_path))
    except ValueError as error:
        return {"status": "invalid_date" if "invalid date" in str(error) else "date_out_of_range", **EMPTY}
    year, month, day = (int(part) for part in date.strip().split("-"))
    for back in range(1, 5):
        earlier = (datetime.date(year, month, day) - datetime.timedelta(days=back)).isoformat()
        try:
            days.append(get_rates(RatesInput(date=earlier, currencies=currencies), tmp_path))
        except ValueError:
            pass
    published = [each for each in days if each.published]
    if not published:
        return {"status": "date_out_of_range", **EMPTY}
    rates = {rate.currency: rate.rate for rate in published[0].rates}
    if not rates[codes[0]] or not rates[codes[1]]:
        return {"status": "no_rate", **EMPTY}
    value = calculate(CalculateInput(expression=f"{amount} * {rates[codes[1]]} / {rates[codes[0]]}"), tmp_path).value
    total = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return converted(codes[0], codes[1], published[0].date, f"{total}")


def test_the_instructions_earn_a_valid_verdict(tmp_path: Path) -> None:
    rng = random.Random(580)
    names = [name for name, _ in NAMES] + NO_CURRENCY + ["EUR", "GBP", "ISK", "RUB", "BGN", "CYP", "TRL", "TRY"]
    trips = [
        SATURDAY,
        ("100", "ISK", "EUR", "2010-06-01"),
        ("1", "usd", "usd", "2016-03-25"),
        ("1", "EUR", "USD", "1999-01-04"),
        ("1", "EUR", "USD", "1999-01-02"),
        ("1", "EUR", "USD", "2026-10-26"),
    ]
    for _ in range(400):
        date = rng.choice(DAYS)[:8] + f"{rng.randint(1, 31):02d}"
        amount = rng.choice(["1000", "25.50", "0", "0.125", "abc", "-3", "1e3", "99999999.99"])
        trips.append((amount, rng.choice(names), rng.choice(names), date))
    seen = set()
    for trip in trips:
        answer = follow_instructions(trip, tmp_path)
        verdict = verify(trip, answer)
        assert verdict["valid"] is True, (trip, answer, verdict)
        seen.add(answer["status"])
    assert seen == set(STATUSES)


@pytest.mark.parametrize(
    "answer",
    [
        {},
        {"status": "converted"},
        {"status": "converted", "from_currency": "USD", "to_currency": "JPY", "rate_date": "2015-03-13"},
        {**RIGHT, "status": "CONVERTED"},
        {**RIGHT, "status": "ok"},
        {**RIGHT, "converted": 121462.35},
        {**RIGHT, "converted": None},
        {**RIGHT, "rate_date": ["2015-03-13"]},
        {**RIGHT, "rate": "128.41"},
        {"status": "too_many_legs", **EMPTY},
    ],
)
def test_a_malformed_answer_never_reaches_the_verifier(answer: dict) -> None:
    # NanoAgent builds every answer into its contract class first, and refuses one that does not fit.
    with pytest.raises(ValueError):
        build_output(answer, ConvertOutput)


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"amount": "1", "from_currency": "USD", "to_currency": "EUR"},
        {"amount": 1, "from_currency": "USD", "to_currency": "EUR", "date": "2020-01-02"},
        {"amount": "1", "from_currency": ["USD"], "to_currency": "EUR", "date": "2020-01-02"},
        {"amount": "1", "from_currency": "USD", "to_currency": "EUR", "date": "2020-01-02", "rate": "1.1"},
    ],
)
def test_a_malformed_task_input_is_refused(arguments: dict) -> None:
    with pytest.raises(ValueError):
        build_output(arguments, ConvertInput)


def check(tool: str, value: dict, output: dict | None = None) -> bool:
    """Whether verify_input (without ``output``) or verify_output (with it) approves a tool call."""
    given, made = TOOLS[Tool(tool)]
    if output is None:
        return verifier.verify_input(tool, build_output(value, given))["valid"]
    return verifier.verify_output(tool, build_output(value, given), build_output(output, made), ".")["valid"]


def test_checks_tool_inputs() -> None:
    for name in ["USD", "yen", "", *NO_CURRENCY]:
        assert check("find_currency", {"name": name}) is True  # the tool says when a name means nothing
    assert check("get_rates", {"date": "2015-03-13", "currencies": ["USD", "XYZ"]}) is True  # the tool says XYZ is none
    assert check("get_rates", {"date": "not a date", "currencies": ["USD"]}) is True
    for bad in [[], ["usd"], ["USD", "USD"], ["US dollar"], ["USD "]]:
        assert check("get_rates", {"date": "2015-03-13", "currencies": bad}) is False
    assert check("calculate", {"expression": "1/0"}) is True  # the tool says it divides by zero


@pytest.mark.parametrize("name", [name for name, codes in NAMES if codes])
def test_approves_every_true_find_currency_output(name: str, tmp_path: Path) -> None:
    output = plain_output(find_currency(CurrencyInput(name=name), tmp_path))
    assert check("find_currency", {"name": name}, output) is True


@pytest.mark.parametrize(
    "date", ["2015-03-13", "2015-03-14", "2010-06-01", "1999-01-04", "2026-10-26", "2016-03-25", " 2020-01-02 "]
)
def test_approves_every_true_get_rates_output(date: str, tmp_path: Path) -> None:
    given = {"date": date, "currencies": ["EUR", "ISK", "USD", "CYP"]}
    output = plain_output(get_rates(build_output(given, RatesInput), tmp_path))
    assert check("get_rates", given, output) is True


@pytest.mark.parametrize("expression", ["1000 * 128.41 / 1.0572", "(1 + 2) * 3", "0", "-1/3", "0.1 + 0.2"])
def test_approves_every_true_calculate_output(expression: str, tmp_path: Path) -> None:
    output = plain_output(calculate(CalculateInput(expression=expression), tmp_path))
    assert check("calculate", {"expression": expression}, output) is True


@pytest.mark.parametrize(
    ("tool", "given", "output"),
    [
        (
            "find_currency",
            {"name": "pound"},
            {
                "name": "pound",
                "currencies": [
                    {
                        "code": "GBP",
                        "name": "Pound sterling",
                        "first_date": "1999-01-04",
                        "last_date": "2026-10-26",
                    }
                ],
            },
        ),  # CYP dropped
        ("find_currency", {"name": "Bitcoin"}, {"name": "Bitcoin", "currencies": []}),  # must fail
        (
            "get_rates",
            {"date": "2015-03-13", "currencies": ["USD"]},
            {
                "date": "2015-03-13",
                "weekday": "Friday",
                "published": True,
                "rates": [{"currency": "USD", "rate": "1.06"}],
            },
        ),
        (
            "get_rates",
            {"date": "2015-03-14", "currencies": ["USD"]},
            {
                "date": "2015-03-14",
                "weekday": "Saturday",
                "published": True,
                "rates": [{"currency": "USD", "rate": "1.0572"}],
            },
        ),  # Friday's rates passed off as Saturday's
        (
            "get_rates",
            {"date": "2015-03-13", "currencies": ["USD"]},
            {
                "date": "2015-03-13",
                "weekday": "Thursday",
                "published": True,
                "rates": [{"currency": "USD", "rate": "1.0572"}],
            },
        ),
        (
            "get_rates",
            {"date": "2010-06-01", "currencies": ["ISK"]},
            {
                "date": "2010-06-01",
                "weekday": "Tuesday",
                "published": True,
                "rates": [{"currency": "ISK", "rate": "160.0"}],
            },
        ),  # made up
        (
            "get_rates",
            {"date": "2030-01-01", "currencies": ["USD"]},
            {"date": "2030-01-01", "weekday": "Tuesday", "published": False, "rates": []},
        ),  # must fail
        ("calculate", {"expression": "1/3"}, {"expression": "1/3", "value": "0.33"}),
        ("calculate", {"expression": "1/0"}, {"expression": "1/0", "value": "0"}),  # must fail
    ],
)
def test_refuses_a_tool_output_that_is_not_the_data(tool: str, given: dict, output: dict) -> None:
    assert check(tool, given, output) is False


def test_expected_matches_the_instructions_example() -> None:
    assert expected(*SATURDAY)[1:] == (
        "1000 USD is 121462.35 JPY at the rates of 2015-03-13",
        "USD",
        "JPY",
        "2015-03-13",
        "121462.35",
    )
