"""Period keys and labels for daily / weekly / monthly snapshots."""

from datetime import datetime, timedelta
from calendar import monthrange


TIME_RANGES = ("daily", "weekly", "monthly")
TIME_RANGE_LABELS = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
}


def period_key(time_range: str, when: datetime | None = None) -> str:
    """Return a sortable period key for the given time range."""
    when = when or datetime.now()
    if time_range == "daily":
        return when.strftime("%Y-%m-%d")
    if time_range == "weekly":
        iso = when.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if time_range == "monthly":
        return when.strftime("%Y-%m")
    raise ValueError(f"Unknown time range: {time_range}")


def period_bounds(time_range: str, key: str) -> tuple[datetime, datetime]:
    """Return inclusive start and exclusive end datetimes for a period key."""
    if time_range == "daily":
        start = datetime.strptime(key, "%Y-%m-%d")
        return start, start + timedelta(days=1)

    if time_range == "weekly":
        year_str, week_str = key.split("-W")
        start = datetime.fromisocalendar(int(year_str), int(week_str), 1)
        return start, start + timedelta(days=7)

    if time_range == "monthly":
        start = datetime.strptime(key, "%Y-%m")
        last_day = monthrange(start.year, start.month)[1]
        end = start.replace(day=last_day) + timedelta(days=1)
        return start, end

    raise ValueError(f"Unknown time range: {time_range}")


def format_period_label(time_range: str, key: str) -> str:
    """Human-readable label for a stored period key."""
    start, end = period_bounds(time_range, key)
    last = end - timedelta(days=1)

    if time_range == "daily":
        return start.strftime("%b %d, %Y")
    if time_range == "weekly":
        if start.year == last.year and start.month == last.month:
            return f"{start.strftime('%b %d')} – {last.strftime('%d, %Y')} ({key})"
        if start.year == last.year:
            return f"{start.strftime('%b %d')} – {last.strftime('%b %d, %Y')} ({key})"
        return f"{start.strftime('%b %d, %Y')} – {last.strftime('%b %d, %Y')} ({key})"
    if time_range == "monthly":
        return start.strftime("%B %Y")
    return key


def parse_count(text: str | None) -> int | None:
    """Extract an integer from GitHub count text such as '1,234' or '123 stars this week'."""
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None
