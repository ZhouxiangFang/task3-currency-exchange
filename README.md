# Currency Exchange

Convert an amount between currencies using historical European Central Bank (ECB) reference rates.
Enter an amount, two currency codes or English names, and a date. The agent looks up the rates and
calculates the conversion. A deterministic verifier checks the answer against the same fixed dataset.

Data covers **January 4, 1999 to October 26, 2026**. Weekends and holidays use the latest earlier
publication date. The plugin runs offline and needs no API key.

## Example

Ask: **Convert 1000 US dollars to yen on March 14, 2015.**

Input:

```json
{"amount": "1000", "from_currency": "US dollars", "to_currency": "yen", "date": "2015-03-14"}
```

Output:

```json
{"status": "converted", "from_currency": "USD", "to_currency": "JPY", "rate_date": "2015-03-13", "converted": "121462.35"}
```

March 14 was a Saturday, so the conversion uses Friday's rates.

## Tools

| Tool | Purpose |
|---|---|
| `find_currency` | Match a code or English name to currencies and their available date ranges. |
| `get_rates` | Read one day's rates in units per euro, or report that no rates were published. |
| `calculate` | Evaluate decimal arithmetic with 28-digit precision. |

The `convert-currency` task uses all three tools. Names ignore case and accents and accept common
plurals. Ambiguous names such as `dollar` require a more specific name or code.

## Conversion rules

1. Use the requested date if rates were published; otherwise use the latest earlier publication date.
2. Calculate `amount * target_rate / source_rate`. EUR has a rate of 1.
3. Round half up to two decimal places for every currency.

A missing currency rate on the selected publication date returns `no_rate`; the agent does not search
further back for that currency. Amounts must be nonnegative plain decimals, such as `1000` or `25.50`.
Commas, signs, and scientific notation are not accepted.

Checks run in this order, with the source currency checked before the target:

| Status | Meaning |
|---|---|
| `invalid_amount` | The amount has an invalid format. |
| `no_such_currency` | A currency code or name is unknown. |
| `ambiguous_currency` | A name matches more than one currency. |
| `invalid_date` | The date is not a valid `YYYY-MM-DD` date. |
| `date_out_of_range` | The date is outside the snapshot. |
| `no_rate` | A currency has no rate on the selected publication date. |
| `converted` | The conversion succeeded. |

For any status other than `converted`, all other output fields must be empty strings.

## Verification

The verifier independently reads the dataset to check the status, currency codes, rate date, and amount.
Amounts within one cent of the expected result are accepted. A conversion with incorrect fields receives
partial credit across three checks: currencies, rate date, and amount. Incorrect statuses are rejected.
Typed contracts reject malformed output, and tool responses are checked against the dataset.

Tests cover missing rates, ambiguous names, invalid inputs, date boundaries, rounding, incorrect answers,
and the agent's lookup procedure. That procedure queries the requested date and four preceding dates
in parallel, covering publication gaps in this snapshot.

## Layout

`contract.py` defines typed inputs and outputs; `nanoagent.yaml` defines tools and task instructions.
Tool implementations live in `src/plugin/`, verification in `verifier/`, and tests in `tests/`.

## Develop and run

Requires Git, uv, and Python 3.12 or later.

```bash
git clone https://github.com/ZhouxiangFang/task3-currency-exchange.git
cd task3-currency-exchange
uv sync --extra dev
uv run pytest
uv run ruff check .
```

Check plugin packaging:

```bash
uvx --from "git+https://github.com/RUSH-LAB/nanoagent#subdirectory=nanoagent" nanoagent plugin inspect .
```

Rebuild the generated data:

```bash
uv run python tests/build_data.py
```

## Data and limitations

Source: European Central Bank. The bundled
[ECB historical rates](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)
snapshot is pinned by SHA-256 in `tests/build_data.py`. It contains 7,122 publication days and 41 currencies
plus EUR. Rates retain the source's decimal text. English currency names and aliases are listed in the
build script; a test checks that `verifier/data.py` matches a fresh rebuild.

These are daily reference rates, not bank quotes or intraday prices. Dates after October 26, 2026 are
unsupported. Some currencies have gaps or no longer have published rates. Name matching uses only the
bundled aliases; use an ISO code when a name is unknown or ambiguous.
