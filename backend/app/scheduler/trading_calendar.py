import logging
from datetime import date

logger = logging.getLogger(__name__)

HOLIDAYS_2025 = {
    date(2025, 1, 1),
    *[date(2025, 1, d) for d in range(28, 32)],
    *[date(2025, 2, d) for d in range(1, 5)],
    date(2025, 4, 4), date(2025, 4, 5), date(2025, 4, 7),
    date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 5),
    date(2025, 6, 2),
    date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3),
    date(2025, 10, 6), date(2025, 10, 7), date(2025, 10, 8),
}

HOLIDAYS_2026 = {
    date(2026, 1, 1), date(2026, 1, 2),
    date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
    date(2026, 2, 19), date(2026, 2, 20), date(2026, 2, 23), date(2026, 2, 24),
    date(2026, 4, 6),
    date(2026, 5, 1), date(2026, 5, 4), date(2026, 5, 5),
    date(2026, 6, 19),
    date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 5),
    date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8), date(2026, 10, 9),
}

HOLIDAYS_2027 = {
    date(2027, 1, 1),
    date(2027, 2, 8), date(2027, 2, 9), date(2027, 2, 10),
    date(2027, 2, 11), date(2027, 2, 12),
    date(2027, 4, 5),
    date(2027, 5, 3),
    date(2027, 6, 14),
    date(2027, 10, 1), date(2027, 10, 4), date(2027, 10, 5),
    date(2027, 10, 6), date(2027, 10, 7),
}

_ALL_HOLIDAYS = HOLIDAYS_2025 | HOLIDAYS_2026 | HOLIDAYS_2027


def is_trading_day(d: date | None = None) -> bool:
    if d is None:
        d = date.today()
    if d.weekday() >= 5:
        return False
    return d not in _ALL_HOLIDAYS
