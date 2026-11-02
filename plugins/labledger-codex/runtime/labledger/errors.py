class LedgerError(Exception):
    """A backend error with a stable response code."""

    code = 2


class Conflict(LedgerError):
    code = 3


class Prerequisite(LedgerError):
    code = 4


class StorageError(LedgerError):
    code = 5
