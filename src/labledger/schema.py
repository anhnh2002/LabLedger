import json
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker

from .errors import LedgerError


def schema():
    return json.loads(files("labledger").joinpath("resources/schema.json").read_text())


def validate(value, kind):
    document = schema()
    validator = Draft202012Validator(
        {"$ref": f"#/$defs/{kind}", "$defs": document["$defs"]},
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(value), key=lambda error: str(list(error.path)))
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, error.path)) or kind}: {error.message}" for error in errors[:8]
        )
        raise LedgerError(details)
