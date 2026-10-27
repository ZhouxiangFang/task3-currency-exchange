"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    FIND_CURRENCY = "find_currency"
    GET_RATES = "get_rates"
    CALCULATE = "calculate"


class Task(Enum):
    CONVERT_CURRENCY = "convert-currency"


class Status(Enum):
    CONVERTED = "converted"
    INVALID_AMOUNT = "invalid_amount"
    NO_SUCH_CURRENCY = "no_such_currency"
    AMBIGUOUS_CURRENCY = "ambiguous_currency"
    INVALID_DATE = "invalid_date"
    DATE_OUT_OF_RANGE = "date_out_of_range"
    NO_RATE = "no_rate"


CURRENCY = "An ISO currency code or English name, such as USD, usd, Japanese yen, or yen"
CODE = "A currency's three-letter ISO code, in capitals, such as USD"
DATE = "A date written YYYY-MM-DD, such as 2015-03-14"
STATUS = (
    "converted: success; invalid_amount: not a nonnegative plain decimal; no_such_currency: unknown currency; "
    "ambiguous_currency: multiple matches; invalid_date: not a valid YYYY-MM-DD date; "
    "date_out_of_range: outside the snapshot; no_rate: a currency has no rate on the selected publication day"
)


@dataclass
class ConvertInput(Output):
    amount: Annotated[str, "How much to convert, a decimal number such as 1000 or 25.50"]
    from_currency: Annotated[str, "Source currency: ISO code or English name"]
    to_currency: Annotated[str, "Target currency: ISO code or English name"]
    date: Annotated[str, "The day of the conversion, written YYYY-MM-DD"]


@dataclass
class ConvertOutput(Output):
    status: Annotated[Status, STATUS]
    from_currency: Annotated[str, "The ISO code of the from currency; empty unless status is converted"]
    to_currency: Annotated[str, "The ISO code of the to currency; empty unless status is converted"]
    rate_date: Annotated[
        str,
        "Latest ECB publication date on or before the requested date; YYYY-MM-DD, or empty unless converted",
    ]
    converted: Annotated[
        str,
        "The converted amount, rounded half up to 2 decimal places, such as 120971.84; empty unless status is converted",
    ]


@dataclass
class CurrencyInput(Output):
    name: Annotated[str, CURRENCY]


@dataclass
class Currency(Output):
    code: Annotated[str, CODE]
    name: Annotated[str, "Its English name"]
    first_date: Annotated[str, "The first day the ECB gave a rate for it, YYYY-MM-DD"]
    last_date: Annotated[
        str, "The last day the ECB gave a rate for it, YYYY-MM-DD; there may be days between without one"
    ]


@dataclass
class CurrencyOutput(Output):
    name: Annotated[str, "The name asked for, unchanged"]
    currencies: Annotated[
        list[Currency], "Every currency the name may mean, sorted by code: one, or several when the name is ambiguous"
    ]


@dataclass
class RatesInput(Output):
    date: Annotated[str, DATE]
    currencies: Annotated[list[str], "Three-letter ISO codes in capitals, such as USD; each once, 1 or more"]


@dataclass
class Rate(Output):
    currency: Annotated[str, CODE]
    rate: Annotated[str, "How many units of it one euro bought, exactly as the ECB wrote it; empty when no rate"]


@dataclass
class RatesOutput(Output):
    date: Annotated[str, "The date asked for, unchanged"]
    weekday: Annotated[str, "Its day of the week, such as Saturday"]
    published: Annotated[bool, "Whether the ECB published rates that day: never on weekends and TARGET holidays"]
    rates: Annotated[list[Rate], "One entry per currency asked for, in the order asked; empty when not published"]


@dataclass
class CalculateInput(Output):
    expression: Annotated[
        str, "Arithmetic on decimal numbers with + - * / and parentheses, such as 1000 * 128.41 / 1.0572"
    ]


@dataclass
class CalculateOutput(Output):
    expression: Annotated[str, "The expression, unchanged"]
    value: Annotated[str, "The result in plain decimal notation, calculated with 28-digit precision"]


TOOLS = {
    Tool.FIND_CURRENCY: (CurrencyInput, CurrencyOutput),
    Tool.GET_RATES: (RatesInput, RatesOutput),
    Tool.CALCULATE: (CalculateInput, CalculateOutput),
}
TASKS = {Task.CONVERT_CURRENCY: (ConvertInput, ConvertOutput)}
