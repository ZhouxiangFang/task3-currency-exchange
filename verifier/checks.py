"""Checks shared by the verifiers and the tools: how a name means a currency, which day's rates a date uses, and exact
decimal arithmetic. Pure functions of their arguments and data.py."""

import re
import unicodedata
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from contract import Status

from .data import CURRENCIES, DATES, RATES

CODE = re.compile(r"^[A-Z]{3}$")
AMOUNT = re.compile(r"^[0-9]+(\.[0-9]+)?$")
DAY = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$")
CENT = Decimal("0.01")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def folded(text):
    """``text`` as names are compared: accents dropped, case folded, runs of spaces made one."""
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).casefold().split())


def names(currencies):
    """Folded name -> the sorted codes of every currency called that: English names and aliases."""
    index = {}
    for code, (name, others) in currencies.items():
        for each in {name, *others}:
            index.setdefault(folded(each), set()).add(code)
    return {name: sorted(codes) for name, codes in index.items()}


def rates(table):
    """code -> its rate on each publication day, in DATES' order: the ECB's text, or "" for none."""
    return {code: ["" if rate == "-" else rate for rate in values.split()] for code, values in table.items()}


NAMES = names(CURRENCIES)
DAYS = DATES.split()
RATE = rates(RATES)


def resolve(text):
    """The sorted codes of every currency ``text`` may mean: empty when none, several when it is ambiguous.

    A three-letter ISO code matches in any case. Otherwise the name matches whatever its case and accents, and a
    plural "s" is dropped if the name with it means nothing ("dollars", "euros").
    """
    plain = text.strip()
    if plain.upper() in CURRENCIES and len(plain) == 3:
        return [plain.upper()]
    key = folded(plain)
    if key in NAMES:
        return NAMES[key]
    if key.endswith("s") and key[:-1] in NAMES:
        return NAMES[key[:-1]]
    return []


def amount_value(text):
    """``text`` as a Decimal if it is a number of zero or more written with digits and at most one point, else None."""
    plain = text.strip()
    return Decimal(plain) if AMOUNT.fullmatch(plain) else None


def leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def real_date(text):
    """``text`` as a YYYY-MM-DD date if it is a real one (spaces around it dropped), else None."""
    found = DAY.fullmatch(text.strip())
    if not found:
        return None
    year, month, day = (int(part) for part in found.groups())
    days = [31, 29 if leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if year < 1 or not 1 <= month <= 12 or not 1 <= day <= days[month - 1]:
        return None
    return text.strip()


def weekday(date):
    """The day of the week of a real YYYY-MM-DD date (Sakamoto's method)."""
    year, month, day = (int(part) for part in date.split("-"))
    offsets = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
    if month < 3:
        year -= 1
    sunday_first = (year + year // 4 - year // 100 + year // 400 + offsets[month - 1] + day) % 7
    return WEEKDAYS[(sunday_first - 1) % 7]


def publication(date):
    """The index in DAYS of the latest publication day on or before ``date`` (binary search), or -1 for none."""
    low, high = 0, len(DAYS)
    while low < high:
        middle = (low + high) // 2
        if DAYS[middle] <= date:
            low = middle + 1
        else:
            high = middle
    return low - 1


def rate_on(code, index):
    """The rate of ``code`` on publication day ``index``: the ECB's text, "1" for the euro, or "" for none."""
    return "1" if code == "EUR" else RATE[code][index]


def known_dates(code):
    """The first and the last day the ECB gave a rate for ``code``."""
    if code == "EUR":
        return DAYS[0], DAYS[-1]
    given = [day for day, rate in zip(DAYS, RATE[code]) if rate]
    return given[0], given[-1]


def codes_problem(codes):
    """What makes ``codes`` no list of currency codes to ask about, or None."""
    if not codes:
        return "name at least one currency"
    malformed = [code for code in codes if not CODE.fullmatch(code)]
    if malformed:
        return f"{malformed} are not ISO codes: a currency code is three capital letters, such as USD"
    repeated = sorted(code for code, count in Counter(codes).items() if count > 1)
    if repeated:
        return f"name each currency once: {repeated} are repeated"
    return None


def converted(amount, from_rate, to_rate):
    """``amount`` in the from currency, in the to currency: amount * to_rate / from_rate, rounded half up to a cent."""
    with localcontext() as context:
        context.prec = 50
        return (amount * Decimal(to_rate) / Decimal(from_rate)).quantize(CENT, rounding=ROUND_HALF_UP)


def expected(amount, from_currency, to_currency, date):
    """The status the conversion has, why, and the from code, to code, rate day and converted amount (empty unless
    converted).

    The checks go in this order, the first that holds deciding: the amount, the from currency, the to currency, the
    date's form, the date's range, then whether both currencies have a rate on the day used.
    """
    nothing = ("", "", "", "")
    value = amount_value(amount)
    if value is None:
        return Status.INVALID_AMOUNT, f"the amount {amount!r} is not a number of zero or more", *nothing
    codes = []
    for role, name in (("from", from_currency), ("to", to_currency)):
        found = resolve(name)
        if not found:
            return Status.NO_SUCH_CURRENCY, f"the {role} currency {name!r} names no currency", *nothing
        if len(found) > 1:
            return Status.AMBIGUOUS_CURRENCY, f"the {role} currency {name!r} may mean any of {found}", *nothing
        codes.append(found[0])
    day = real_date(date)
    if day is None:
        return Status.INVALID_DATE, f"the date {date!r} is not a real YYYY-MM-DD date", *nothing
    index = publication(day)
    if index < 0 or day > DAYS[-1]:
        return Status.DATE_OUT_OF_RANGE, f"{day} is outside the ECB rates, {DAYS[0]} to {DAYS[-1]}", *nothing
    missing = [code for code in codes if not rate_on(code, index)]
    if missing:
        return Status.NO_RATE, f"the ECB gave no rate for {missing[0]} on {DAYS[index]}", *nothing
    total = converted(value, rate_on(codes[0], index), rate_on(codes[1], index))
    fact = f"{value} {codes[0]} is {total} {codes[1]} at the rates of {DAYS[index]}"
    return Status.CONVERTED, fact, codes[0], codes[1], DAYS[index], f"{total}"


TOKEN = re.compile(r"\s*(?:([0-9]+(?:\.[0-9]*)?|\.[0-9]+)|(.))")


def tokens(expression):
    found = []
    for number, other in TOKEN.findall(expression):
        if number:
            found.append(Decimal(number))
        elif other.strip():
            if other not in "+-*/()":
                raise ValueError(f"{other!r} is not a number, + - * /, or a parenthesis")
            found.append(other)
    return found


def evaluate(expression):
    """The exact value of ``expression`` (+ - * / and parentheses on decimal numbers) to 28 significant digits, in
    plain decimal notation; raises ValueError when it is not one or divides by zero."""
    items = tokens(expression)
    position = 0

    def peek():
        return items[position] if position < len(items) else None

    def take():
        nonlocal position
        position += 1
        return items[position - 1]

    def atom():
        item = peek()
        if item == "-":
            take()
            return -atom()
        if item == "+":
            take()
            return atom()
        if item == "(":
            take()
            value = total()
            if peek() != ")":
                raise ValueError("a parenthesis is not closed")
            take()
            return value
        if isinstance(item, Decimal):
            return take()
        raise ValueError("the expression is incomplete")

    def product():
        value = atom()
        while peek() in ("*", "/"):
            if take() == "*":
                value = value * atom()
            else:
                divisor = atom()
                if divisor == 0:
                    raise ValueError("division by zero")
                value = value / divisor
        return value

    def total():
        value = product()
        while peek() in ("+", "-"):
            value = value + product() if take() == "+" else value - product()
        return value

    with localcontext() as context:
        context.prec = 28
        try:
            value = total()
        except InvalidOperation as error:
            raise ValueError("the expression is not arithmetic on decimal numbers") from error
        if position != len(items):
            raise ValueError("the expression has something left over after its end")
        return format(value.normalize(), "f") if value else "0"
