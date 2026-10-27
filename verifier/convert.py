"""The convert-currency task's check: the status the data gives, and for a conversion the right currencies, the right
day's rates, and the amount to the cent."""

from contract import Status

from .checks import CENT, amount_value, expected, result


def verify_task(arguments, output, reference, workspace):
    """``output``: a contract ConvertOutput, judged against the data itself (the task has no reference tool)."""
    status, fact, from_code, to_code, rate_date, total = expected(
        arguments.amount, arguments.from_currency, arguments.to_currency, arguments.date
    )
    given = [output.from_currency, output.to_currency, output.rate_date, output.converted]
    if output.status is not status:
        return result(False, f"{fact}, so the status is {status.value}, but the answer says {output.status.value}")
    if status is not Status.CONVERTED:
        if any(given):
            return result(False, f"every other field must be empty unless status is converted; {fact}")
        return result(True, f"{fact}, as the answer says")
    value = amount_value(output.converted)
    checks = {
        "currencies": [output.from_currency, output.to_currency] == [from_code, to_code],
        "rate_date": output.rate_date == rate_date,
        "converted": value is not None and abs(value - amount_value(total)) <= CENT,
    }
    wrong = [name for name, right in checks.items() if not right]
    if wrong:
        expected_fields = {
            "from_currency": from_code,
            "to_currency": to_code,
            "rate_date": rate_date,
            "converted": total,
        }
        return result(
            False,
            f"{', '.join(wrong)} wrong: {fact}",
            score=1 - len(wrong) / len(checks),
            expected=expected_fields,
        )
    return result(True, f"{fact}, as the answer says")
