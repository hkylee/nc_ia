"""Timezone helpers shared by web and policy authoring entrypoints."""

from __future__ import annotations

import os
import time


DEFAULT_APP_TIMEZONE = "Asia/Seoul"


def configure_local_timezone(default: str = DEFAULT_APP_TIMEZONE) -> str:
    """Configure process-local time functions to use the service timezone."""

    timezone = str(os.environ.get("NC_TIMEZONE") or default).strip() or default
    os.environ["TZ"] = timezone
    if hasattr(time, "tzset"):
        time.tzset()
    return timezone
