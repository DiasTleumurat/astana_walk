"""Conservative subset of OSM opening_hours; unsupported expressions stay unknown."""
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Asia/Almaty')
DAYS = {'Mo': 0, 'Tu': 1, 'We': 2, 'Th': 3, 'Fr': 4, 'Sa': 5, 'Su': 6}


def parse_hours(raw):
    if raw == '24/7':
        return [(set(range(7)), 0, 1440)]
    if not raw:
        return None
    intervals = []
    for clause in raw.split(';'):
        match = re.fullmatch(r'\s*(?:(Mo|Tu|We|Th|Fr|Sa|Su)(?:-(Mo|Tu|We|Th|Fr|Sa|Su))?\s+)?(\d{2}:\d{2}-\d{2}:\d{2}(?:,\s*\d{2}:\d{2}-\d{2}:\d{2})*)\s*', clause)
        if not match:
            return None
        start_day, end_day, times = match.groups()
        if start_day:
            first, last = DAYS[start_day], DAYS[end_day or start_day]
            days = {(first + i) % 7 for i in range((last - first) % 7 + 1)}
        else:
            days = set(range(7))
        for timespan in times.split(','):
            values = timespan.strip().split('-')
            minutes = []
            for value in values:
                h, m = map(int, value.split(':'))
                if h > 24 or m > 59 or (h == 24 and m != 0):
                    return None
                minutes.append(60 * h + m)
            if minutes[0] == minutes[1] or minutes[0] == 1440:
                return None
            intervals.append((days, *minutes))
    return intervals


def status_at(raw, when):
    intervals = parse_hours(raw)
    if intervals is None:
        return 'unknown'
    local = when.astimezone(ZONE)
    minute = local.hour * 60 + local.minute
    for days, start, end in intervals:
        if start < end and local.weekday() in days and start <= minute < end:
            return 'open'
        if end < start and ((local.weekday() in days and minute >= start) or ((local.weekday() - 1) % 7 in days and minute < end)):
            return 'open'
    return 'closed'


def visit_status(raw, arrival, duration):
    states = {status_at(raw, arrival + timedelta(minutes=m)) for m in range(duration + 1)}
    return 'unknown' if 'unknown' in states else ('closed' if 'closed' in states else 'open')
