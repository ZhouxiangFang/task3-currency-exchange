"""The tool calls' checks: every list of codes is well formed, and each output is exactly what the data says."""

from contract import Tool

from .checks import (
    CURRENCIES,
    DAYS,
    codes_problem,
    evaluate,
    known_dates,
    publication,
    rate_on,
    real_date,
    resolve,
    result,
    weekday,
)


def verify_input(tool, value):
    # Any name, date or expression may be asked about: the tool itself says when it means nothing.
    if tool is Tool.GET_RATES:
        problem = codes_problem(value.currencies)
        if problem:
            return result(False, problem, given=value.currencies)
    return result(True, "input is valid")


def verify_output(tool, input_value, output_value, workspace):
    if tool is Tool.FIND_CURRENCY:
        return verify_currency(input_value.name, output_value)
    if tool is Tool.CALCULATE:
        try:
            value = evaluate(input_value.expression)
        except ValueError:
            return result(False, f"{input_value.expression!r} cannot be worked out, so the tool must fail, not answer")
        if output_value.expression != input_value.expression or output_value.value != value:
            return result(False, f"{input_value.expression} is {value}", given=output_value.value)
        return result(True, "output is valid")
    return verify_rates(input_value, output_value)


def verify_currency(name, output_value):
    codes = resolve(name)
    if not codes:
        return result(False, f"{name!r} names no currency, so the tool must fail, not answer")
    expected = [(code, CURRENCIES[code][0], *known_dates(code)) for code in codes]
    given = [(each.code, each.name, each.first_date, each.last_date) for each in output_value.currencies]
    if output_value.name != name or given != expected:
        return result(False, f"{name!r} means {codes}", expected=expected, given=given)
    return result(True, "output is valid")


def verify_rates(input_value, output_value):
    day = real_date(input_value.date)
    unknown = sorted(code for code in input_value.currencies if code not in CURRENCIES)
    if day is None or not DAYS[0] <= day <= DAYS[-1] or unknown:
        return result(False, "the date or a currency is not one the data covers, so the tool must fail, not answer")
    index = publication(day)
    published = DAYS[index] == day
    expected = [(code, rate_on(code, index)) for code in input_value.currencies] if published else []
    given = [(each.currency, each.rate) for each in output_value.rates]
    fields = (output_value.date, output_value.weekday, output_value.published)
    if fields != (input_value.date, weekday(day), published) or given != expected:
        return result(False, "get_rates must give exactly what the data says", expected=expected, given=given)
    return result(True, "output is valid")
