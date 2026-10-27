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


CURRENCY = (
    "A currency: its ISO code such as USD or usd, its name such as Japanese yen, a common name such as yen or "
    "dollars, or its Chinese name such as 日元"
)
CODE = "A currency's three-letter ISO code, in capitals, such as USD"
DATE = "A date written YYYY-MM-DD, such as 2015-03-14"
STATUS = (
    "converted: the conversion was made; invalid_amount: the amount is not a number of zero or more; "
    "no_such_currency: the from currency, or else the to currency, names no currency; ambiguous_currency: it names "
    "more than one; invalid_date: the date is not a real YYYY-MM-DD date; date_out_of_range: no ECB rates were "
    "published on or before it, or it is after the last day the data covers; no_rate: the ECB gave no rate for one "
    "of the currencies on the day the conversion uses"
)


@dataclass
class ConvertInput(Output):
    amount: Annotated[str, "How much to convert, a decimal number such as 1000 or 25.50"]
    from_currency: Annotated[
        str, "The currency the amount is in: its ISO code, its name, a common name, or its Chinese name"
    ]
    to_currency: Annotated[
        str, "The currency to convert into: its ISO code, its name, a common name, or its Chinese name"
    ]
    date: Annotated[str, "The day of the conversion, written YYYY-MM-DD"]


@dataclass
class ConvertOutput(Output):
    status: Annotated[Status, STATUS]
    from_currency: Annotated[str, "The ISO code of the from currency; empty unless status is converted"]
    to_currency: Annotated[str, "The ISO code of the to currency; empty unless status is converted"]
    rate_date: Annotated[
        str,
        "The ECB publication day whose rates were used, YYYY-MM-DD: the date itself if rates were published that day, "
        "else the latest earlier publication day; empty unless status is converted",
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
    chinese_name: Annotated[str, "Its Chinese name"]
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
    value: Annotated[str, "Its exact value to 28 significant digits, in plain decimal notation"]


TOOLS = {
    Tool.FIND_CURRENCY: (CurrencyInput, CurrencyOutput),
    Tool.GET_RATES: (RatesInput, RatesOutput),
    Tool.CALCULATE: (CalculateInput, CalculateOutput),
}
TASKS = {Task.CONVERT_CURRENCY: (ConvertInput, ConvertOutput)}
