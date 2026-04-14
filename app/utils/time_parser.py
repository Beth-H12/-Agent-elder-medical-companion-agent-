from datetime import date, datetime, time, timedelta
from typing import Iterable, Optional, Tuple

from app.core.config import settings


def parse_preferred_window(
    preferred_time: Optional[str], reference_date: Optional[date] = None
) -> Tuple[date, Optional[Tuple[time, time]]]:
    if reference_date is None:
        reference_date = settings.demo_reference_date

    preferred_time = preferred_time or "明天上午"
    target_date = reference_date

    if "后天" in preferred_time:
        target_date = reference_date + timedelta(days=2)
    elif "明天" in preferred_time:
        target_date = reference_date + timedelta(days=1)
    elif "今天" in preferred_time:
        target_date = reference_date
    else:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                target_date = datetime.strptime(preferred_time[:10], fmt).date()
                break
            except ValueError:
                continue

    if "上午" in preferred_time or "早上" in preferred_time:
        return target_date, (time(hour=8), time(hour=12))
    if "下午" in preferred_time:
        return target_date, (time(hour=12), time(hour=17, minute=30))
    if "晚上" in preferred_time:
        return target_date, (time(hour=17, minute=30), time(hour=20))
    return target_date, None


def choose_best_slot(
    slots: Iterable[str], preferred_time: Optional[str], reference_date: Optional[date] = None
) -> Optional[str]:
    target_date, window = parse_preferred_window(preferred_time, reference_date)
    parsed_slots = [datetime.strptime(slot, "%Y-%m-%d %H:%M") for slot in slots]

    same_day_slots = [slot for slot in parsed_slots if slot.date() == target_date]
    if window:
        start, end = window
        window_slots = [
            slot
            for slot in same_day_slots
            if start <= slot.time() <= end
        ]
        if window_slots:
            return min(window_slots).strftime("%Y-%m-%d %H:%M")

    if same_day_slots:
        return min(same_day_slots).strftime("%Y-%m-%d %H:%M")

    if parsed_slots:
        return min(parsed_slots).strftime("%Y-%m-%d %H:%M")

    return None


def minus_minutes(slot: str, minutes: int) -> str:
    appointment_time = datetime.strptime(slot, "%Y-%m-%d %H:%M")
    return (appointment_time - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M")
