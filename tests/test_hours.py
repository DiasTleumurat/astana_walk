from datetime import datetime, timezone
import pytest
from backend.hours import parse_hours, status_at, visit_status


@pytest.mark.parametrize('raw', [None, '', 'sunrise-sunset', 'Mo-Fr 10:00-20:00; PH off', '25:00-26:00', 'closed', '09:99-20:00'])
def test_unsupported_unknown(raw):
    assert parse_hours(raw) is None


def test_timezone_and_overnight():
    # Monday 22:30 in Astana, then Tuesday 01:30.
    assert status_at('Mo 22:00-02:00', datetime(2026, 10, 19, 17, 30, tzinfo=timezone.utc)) == 'open'
    assert status_at('Mo 22:00-02:00', datetime(2026, 10, 19, 20, 30, tzinfo=timezone.utc)) == 'open'
    assert status_at('Mo 22:00-02:00', datetime(2026, 10, 19, 22, 0, tzinfo=timezone.utc)) == 'closed'


def test_visit_must_finish_before_closing():
    arrival = datetime(2026, 10, 19, 14, 50, tzinfo=timezone.utc)  # 19:50 local
    assert visit_status('09:00-20:00', arrival, 30) == 'closed'
    assert visit_status('24/7', arrival, 60) == 'open'
