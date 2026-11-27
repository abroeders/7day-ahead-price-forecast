"""Errors of the forecast client."""


class ForecastError(Exception):
    """A forecast could not be read or is invalid."""


class FormulaError(Exception):
    """A price formula is invalid; position is the 0-based character index."""

    def __init__(self, message: str, position: int = 0) -> None:
        super().__init__(f"{message} at position {position}")
        self.message = message
        self.position = position
