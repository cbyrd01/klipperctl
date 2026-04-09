"""Message filtering for console and log output.

Provides reusable filtering for GCode responses: regex include/exclude
patterns and a shorthand to hide Klipper temperature reports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Klipper temperature report pattern:
#   "ok T:210.5 /210.0 B:60.1 /60.0"
#   "T:210.5 /210.0"
#   "T0:210.5 /210.0 T1:195.0 /195.0 B:60.1 /60.0"
#   " T:25.0 /0.0 B:25.0 /0.0"
TEMP_REPORT_PATTERN = re.compile(r"(?:^|\s)(?:ok\s+)?[TB]\d*\s*:\s*[\d.]+\s*/\s*[\d.]+")


@dataclass
class MessageFilter:
    """Filter for console/log messages."""

    include: re.Pattern[str] | None = None
    exclude: re.Pattern[str] | None = None
    exclude_temps: bool = False

    def matches(self, message: str) -> bool:
        """Return True if the message should be displayed."""
        if self.exclude_temps and TEMP_REPORT_PATTERN.search(message):
            return False
        if self.exclude and self.exclude.search(message):
            return False
        return not (self.include and not self.include.search(message))


def build_filter(
    filter_pattern: str | None,
    exclude_pattern: str | None,
    exclude_temps: bool,
) -> MessageFilter:
    """Build a MessageFilter from CLI option values."""
    return MessageFilter(
        include=re.compile(filter_pattern, re.IGNORECASE) if filter_pattern else None,
        exclude=re.compile(exclude_pattern, re.IGNORECASE) if exclude_pattern else None,
        exclude_temps=exclude_temps,
    )
