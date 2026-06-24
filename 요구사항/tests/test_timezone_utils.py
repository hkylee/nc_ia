import os
from datetime import datetime

from src.timezone_utils import configure_local_timezone


def test_configure_local_timezone_defaults_to_korea_time(monkeypatch):
    monkeypatch.delenv("NC_TIMEZONE", raising=False)

    timezone = configure_local_timezone()

    assert timezone == "Asia/Seoul"
    assert os.environ["TZ"] == "Asia/Seoul"
    assert datetime.now().astimezone().utcoffset().total_seconds() == 9 * 60 * 60
