"""The tools that read the ECB rates, from verifier/data.py: the one copy, which the verifier also judges by. Names,
dates and arithmetic follow verifier/checks.py's rules, so a tool and a verdict never disagree on them."""

from __future__ import annotations

from pathlib import Path

from contract import (
    CalculateInput,
    CalculateOutput,
    Currency,
    CurrencyInput,
    CurrencyOutput,
    Rate,
    RatesInput,
    RatesOutput,
)
from verifier.checks import (
    CURRENCIES,
    DAYS,
    codes_problem,
    evaluate,
    known_dates,
    publication,
    rate_on,
    real_date,
    resolve,
    weekday,
)


def find_currency(given: CurrencyInput, workspace: Path) -> CurrencyOutput:
    codes = resolve(given.name)
    if not codes:
        raise ValueError(
            f"no such currency: {given.name!r}. Use an ISO code such as USD or an English name such as yen."
        )
    currencies = [
        Currency(
            code=code,
            name=CURRENCIES[code][0],
            first_date=known_dates(code)[0],
            last_date=known_dates(code)[1],
        )
        for code in codes
    ]
    return CurrencyOutput(name=given.name, currencies=currencies)


def get_rates(given: RatesInput, workspace: Path) -> RatesOutput:
    problem = codes_problem(given.currencies)
    if problem:
        raise ValueError(problem)
    unknown = sorted(code for code in given.currencies if code not in CURRENCIES)
    if unknown:
        raise ValueError(f"no such currency: {unknown} are not codes the ECB data covers; find_currency gives codes")
    day = real_date(given.date)
    if day is None:
        raise ValueError(f"invalid date: {given.date!r} is not a real date written YYYY-MM-DD")
    if not DAYS[0] <= day <= DAYS[-1]:
        raise ValueError(f"date out of range: the ECB rates run from {DAYS[0]} to {DAYS[-1]}")
    index = publication(day)
    published = DAYS[index] == day
    rates = [Rate(currency=code, rate=rate_on(code, index)) for code in given.currencies] if published else []
    return RatesOutput(date=given.date, weekday=weekday(day), published=published, rates=rates)


def calculate(given: CalculateInput, workspace: Path) -> CalculateOutput:
    return CalculateOutput(expression=given.expression, value=evaluate(given.expression))
