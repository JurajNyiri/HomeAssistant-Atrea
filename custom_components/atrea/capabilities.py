"""Installed-component checks using RD5 configuration registers.

Missing/unknown configuration keeps legacy register-based discovery. Explicit
absence suppresses discovery and makes an existing entity unavailable; registry
entries and user overrides are never deleted.
"""


def _integer(status, register):
    try:
        return int(status[register])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def supports_register(status, register):
    """Return whether the configured unit can use this telemetry register."""
    if register == "H10202":  # SA1: electric or liquid preheater
        return _integer(status, "H10504") != 0
    if register in ("H10205", "H10206"):
        return _integer(status, "H11800") != 0
    if register == "H10204":
        return (_integer(status, "C10509") == 1
                or _integer(status, "H11700") != 0)
    if register == "H10203":  # SA2 can serve the primary or backup heater
        return not (_integer(status, "H10503") == 0
                    and _integer(status, "H10517") == 0)
    if register == "C10215":  # Heat pump / combined heater demand
        return _integer(status, "H10503") not in (0, 1, 2, 3, 4)
    if register == "C10216":  # Water or DX cooling demand
        return _integer(status, "H10507") != 0
    if register == "D10207":  # Heat-pump defrost input
        heater = _integer(status, "H10503")
        cooler = _integer(status, "H10507")
        return not (heater in (0, 1, 2, 3, 4) and cooler in (0, 1))
    if register in ("I11600", "I11601", "I11602", "I11603", "I11604", "I11605"):
        # Standard constant flow = 1; Power_2Z constant flow = 4.
        flow = _integer(status, "H10510")
        if flow not in (1, 4):
            return False
        if flow == 4 and _integer(status, "C10509") != 1:
            return False
        if register in ("I11604", "I11605"):
            return _integer(status, "C10509") != 0
    return True
