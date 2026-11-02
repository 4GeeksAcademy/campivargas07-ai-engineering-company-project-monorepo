"""RFP domain errors."""
from __future__ import annotations


class RfpNotFoundError(Exception):
    pass


class RfpInvalidTransitionError(Exception):
    pass


class RfpValidationError(Exception):
    pass
