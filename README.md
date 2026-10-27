# Currency Exchange

A `nanoagent.plugin/v0001` plugin. The agent is given an amount, two currencies and a date. Each currency may be an
ISO code (`USD`), a name (`Japanese yen`, `yen`, `dollars`) or a Chinese name (`日元`). The agent converts the amount
at the European Central Bank's euro reference rates of that date, or of the last day before it that the ECB published
rates, or says why it cannot. The rates come from a frozen snapshot of the ECB's history, 1999 to 2026, which the agent
can only read through the tools. A deterministic verifier, with no model, checks the answer against that snapshot.

## Tools

| Tool | Does |
|---|---|
| `find_currency` | Gives every currency a name may mean, with its English and Chinese names and the first and last days it has rates. Several currencies means the name is ambiguous. Fails with "no such currency" when it means nothing |
| `get_rates` | Gives the ECB's rates for some currencies on one day: how many units one euro bought, or nothing on a weekend or holiday, or an empty rate when the ECB gave none for a currency |
| `calculate` | Works out `+ - * /` arithmetic on decimal numbers exactly, to 28 significant digits |

| Task | Does |
|---|---|
| `convert-currency` | Converts an amount between two currencies at the ECB rates of a date, or says why it cannot. Runner `agent`, with all three tools |

Input: `{"amount": "1000", "from_currency": "US dollars", "to_currency": "yen", "date": "2015-03-14"}`.
Output: `{"status": "converted", "from_currency": "USD", "to_currency": "JPY", "rate_date": "2015-03-13", "converted": "121462.35"}`,
or another status with every other field empty.

### How a conversion is worked out

The ECB publishes, on each working day, how many units of each currency one euro buys. So:

1. **The rate day** is the date itself if the ECB published that day. Otherwise it is the latest earlier day it
   published. 2015-03-14 was a Saturday, so the rates of Friday 2015-03-13 apply. The longest gap in the data is five
   days, over Easter.
2. **The converted amount** is `amount * to_rate / from_rate` with the rate day's rates, where the euro's rate is 1.
   It is rounded half up to two decimal places: 1000 × 128.41 / 1.0572 = 121462.353…, which rounds to 121462.35.

### Statuses: every edge case

The checks run in this order, and the first that holds decides the status:

| Status | When | Examples |
|---|---|---|
| `invalid_amount` | The amount is not digits with at most one decimal point | `abc`, `-5`, `1,000`, `1e3` |
| `no_such_currency` | The from currency, or else the to currency, means nothing | `Bitcoin`, `BTC`, `us` |
| `ambiguous_currency` | It means more than one currency | `dollar` (USD, AUD, CAD, HKD, NZD, SGD), `pound` (GBP, CYP), `克朗` (seven krone, krona and koruna) |
| `invalid_date` | The date is not a real date written `YYYY-MM-DD` | `2021-02-29`, `2015-13-01`, `March 14, 2015` |
| `date_out_of_range` | No rates were published on or before it, or it is after the data's last day | `1999-01-01` (the first rates are from 1999-01-04); `2030-01-01` |
| `no_rate` | The ECB gave no rate for one of the currencies on the rate day | `ISK` in 2010 (none from 2008-12-10 to 2018-01-31); `RUB` after 2022-03-01; `BGN` in 2026, after Bulgaria took the euro; `CYP` in 2008 |
| `converted` | Otherwise | `1000 US dollars` to `yen` on `2015-03-14`; `usd` to `usd` on Good Friday 2016; `0` of anything |

### How the verifier judges an answer

The verifier works out the status, the rate day and the amount from the snapshot. For `converted` it checks three
things: the two ISO codes, the rate day, and the amount to within one cent, which allows for rounding along the way.
An answer that gets some of them right scores the share it gets right. For example, using the Saturday's date as the
rate day scores 2/3. Every other status requires every other field to be empty. A malformed answer, such as an unknown
status, a number instead of text, or an extra field, is refused before it reaches the verifier.

Every tool output is checked against the same data. A `get_rates` input must name at least one well-formed code, each
once. A well-formed code that the data does not cover passes that check, and the tool itself then fails with "no such
currency".

### Keeping within the agent's limits

The task's instructions take at most three turns of tool calls, plus the submit, well within RUSH Lab's six model
turns per attempt:

1. Look up both currencies.
2. Get the rates of the date and of the four days before it, all at once. No gap is longer than that.
3. Calculate.

The tests play these instructions through the tools on 406 conversions, and every answer earns a valid verdict.

## Layout

```text
.
├── nanoagent.yaml        # manifest: tools, tasks, permissions
├── contract.py           # each tool's and task's typed input and output
├── src/plugin/           # the MCP server and the tools
├── verifier/             # the deterministic verifier; data.py is the rates and the currencies
├── tests/                # tests for the data, the tools and the verifier
│   ├── ecb/              # the frozen snapshot: eurofxref-hist.csv
│   └── build_data.py     # builds verifier/data.py from the snapshot, with the currency names
├── ui/                   # how results are drawn
└── product/              # the product page
```

## Develop and run

You need Git, [uv](https://docs.astral.sh/uv/) and Python 3.12 or later (uv fetches Python if needed). The plugin
needs no network access or API key at run time.

```bash
git clone https://github.com/ZhouxiangFang/task3-currency-exchange.git
cd task3-currency-exchange
uv sync --extra dev
uv run pytest
uv run ruff check .
```

To check the plugin against every NanoAgent publishing rule:

```bash
uvx --from "git+https://github.com/RUSH-LAB/nanoagent#subdirectory=nanoagent" nanoagent plugin inspect .
```

To rebuild `verifier/data.py` from the snapshot (a test checks that it matches):

```bash
uv run python tests/build_data.py
```

On RUSH Lab, open the plugin and ask its chat, for example, "How many yen was 1000 US dollars on 2015-03-14?" The
result card shows the verifier's verdict.

## Data

The data is `eurofxref-hist.csv` from the ECB's
[euro foreign exchange reference rates](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html),
downloaded on 2026-10-26 and pinned in `tests/build_data.py` by SHA-256. The ECB permits reuse with the source
acknowledged: *Source: European Central Bank*. It covers 7,122 publication days, from 1999-01-04 to 2026-10-26, and
41 currencies besides the euro. Rates are kept exactly as the ECB wrote them, as text. The currency names, in
English and Chinese, with the other names people use, are a table in `tests/build_data.py`.

## Limitations

- The rates are the ECB's daily reference rates, set around 14:15 CET. They are not market rates at any other time
  of day, and not what a bank or exchange office charges.
- The data ends on 2026-10-26, and later dates are `date_out_of_range`.
- A name means only what the table lists. `Polish złoty` matches nothing, because the table writes it `zloty`
  and ł is not an accented l.
- The amount must be written in plain digits. `1,000` is `invalid_amount`, since a comma may mean a thousands
  separator or a decimal point.
