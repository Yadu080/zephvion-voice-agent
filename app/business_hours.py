"""Business-hours awareness for the 24/7 receptionist behaviour."""

import datetime

from app import config

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _closing_hour(weekday: int) -> int:
    # Saturday commonly closes earlier than weekdays.
    if weekday == 5:
        return config.SATURDAY_END_HOUR
    return config.BUSINESS_END_HOUR


def is_open(moment: datetime.datetime | None = None) -> bool:
    now = moment or datetime.datetime.now(config.timezone())
    if now.weekday() not in config.BUSINESS_DAYS:
        return False
    return config.BUSINESS_START_HOUR <= now.hour < _closing_hour(now.weekday())


def next_opening(moment: datetime.datetime | None = None) -> datetime.datetime:
    now = moment or datetime.datetime.now(config.timezone())
    candidate = now

    # If today is a business day and we're before opening, we open later today.
    if (now.weekday() in config.BUSINESS_DAYS
            and now.hour < config.BUSINESS_START_HOUR):
        return candidate.replace(hour=config.BUSINESS_START_HOUR, minute=0, second=0, microsecond=0)

    # Otherwise walk forward to the next business day.
    for _ in range(1, 8):
        candidate = candidate + datetime.timedelta(days=1)
        if candidate.weekday() in config.BUSINESS_DAYS:
            return candidate.replace(
                hour=config.BUSINESS_START_HOUR, minute=0, second=0, microsecond=0
            )
    return now


def status() -> dict:
    now = datetime.datetime.now(config.timezone())
    open_now = is_open(now)
    reopens = next_opening(now)
    return {
        "open": open_now,
        "local_time": now.strftime("%A %d %B %Y, %I:%M %p"),
        "reopens_at": reopens.strftime("%A at %I:%M %p"),
        "hours_summary": hours_summary(),
    }


def hours_summary() -> str:
    days = [DAY_NAMES[d] for d in sorted(config.BUSINESS_DAYS)]
    weekday_part = (
        f"{days[0]} to {days[-2]} {config.BUSINESS_START_HOUR}:00-{config.BUSINESS_END_HOUR}:00"
        if len(days) > 1 else f"{days[0]} {config.BUSINESS_START_HOUR}:00-{config.BUSINESS_END_HOUR}:00"
    )
    if 5 in config.BUSINESS_DAYS:
        return f"{weekday_part}, Saturday {config.BUSINESS_START_HOUR}:00-{config.SATURDAY_END_HOUR}:00"
    return weekday_part
